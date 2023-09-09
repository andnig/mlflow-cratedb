def patch_raise_for_status():
    """
    Patch the `crate.client.http._raise_for_status` function to properly raise
    SQLAlchemy's `IntegrityError` exceptions for CrateDB's `DuplicateKeyException`
    errors.

    It is needed to make the `check_uniqueness` machinery work, which is emulating
    UNIQUE constraints on table columns.

    https://github.com/crate-workbench/mlflow-cratedb/issues/9

    TODO: Submit to `crate-python` as a bugfix patch.
    """
    import crate.client.http as http

    _raise_for_status_dist = http._raise_for_status

    def _raise_for_status(response):
        from crate.client.exceptions import IntegrityError, ProgrammingError

        try:
            return _raise_for_status_dist(response)
        except ProgrammingError as ex:
            if "DuplicateKeyException" in ex.message:
                raise IntegrityError(ex.message, error_trace=ex.error_trace) from ex
            raise

    http._raise_for_status = _raise_for_status


def check_uniqueness_factory(sa_entity, attribute_name):
    """
    Run a manual column value uniqueness check on a table, and raise an IntegrityError if applicable.

    CrateDB does not support the UNIQUE constraint on columns. This attempts to emulate it.

    TODO: Submit patch to `crate-python`, to be enabled by a
          dialect parameter `crate_translate_unique` or such.
    """

    def check_uniqueness(mapper, connection, target):
        from sqlalchemy.exc import IntegrityError

        if isinstance(target, sa_entity):
            # TODO: How to use `session.query(SqlExperiment)` here?
            stmt = (
                mapper.selectable.select()
                .filter(getattr(sa_entity, attribute_name) == getattr(target, attribute_name))
                .compile(bind=connection.engine)
            )
            results = connection.execute(stmt)
            if results.rowcount > 0:
                raise IntegrityError(
                    statement=stmt,
                    params=[],
                    orig=Exception(f"DuplicateKeyException on column: {target.__tablename__}.{attribute_name}"),
                )

    return check_uniqueness