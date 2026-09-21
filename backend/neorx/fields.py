"""Django CI field: randomized ciphertext plus a separate keyed search index."""
from django.db import models
from django.db.models import Lookup
from django.db.models.expressions import Col
from .encryption import encrypt_text, decrypt_text, ci_digest, normalize_ci


class EncryptedCIField(models.CharField):
    def get_internal_type(self):
        # Tokens exceed the logical CI max_length; store in an unbounded TEXT column.
        return "TextField"

    def from_db_value(self, value, expression, connection):
        return None if value is None else decrypt_text(value)

    def get_db_prep_save(self, value, connection):
        if hasattr(value, "as_sql"):
            raise ValueError("CI expressions are unsupported; save the logical value through Paciente.")
        return None if value is None else encrypt_text(value)


class CIExact(Lookup):
    lookup_name = "exact"
    prepare_rhs = False

    def index_column(self, compiler):
        if not isinstance(self.lhs, Col):
            raise ValueError("CI lookup requires a direct field column.")
        field = self.lhs.target.model._meta.get_field("ci_search_hash")
        return compiler.compile(Col(self.lhs.alias, field))

    def as_sql(self, compiler, connection):
        sql, params = self.index_column(compiler)
        return f"{sql} = %s", [*params, ci_digest(self.rhs)]


class CIIExact(CIExact):
    lookup_name = "iexact"


class CIContains(CIExact):
    lookup_name = "icontains"

    def as_sql(self, compiler, connection):
        # Preserve existing partial search without a plaintext or substring index.
        # This scan is intentionally limited to the patient CI column in process memory.
        owner = self.lhs.target.model
        quote = connection.ops.quote_name
        table = quote(owner._meta.db_table)
        column = quote(self.lhs.target.column)
        index = quote(owner._meta.get_field("ci_search_hash").column)
        term = normalize_ci(self.rhs)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {column}, {index} FROM {table}")
            matches = [digest for encrypted, digest in cursor.fetchall()
                       if term in normalize_ci(decrypt_text(encrypted))]
        if not matches:
            return "0=1", []
        sql, params = self.index_column(compiler)
        return f"{sql} IN ({', '.join(['%s'] * len(matches))})", [*params, *matches]


class CIContainsCase(CIContains):
    lookup_name = "contains"


for lookup in (CIExact, CIIExact, CIContains, CIContainsCase):
    EncryptedCIField.register_lookup(lookup)
