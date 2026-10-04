class InsufficientVaultRoleError(PermissionError): pass


class NodePatchConflictError(Exception):
    """A patch precondition failed; no changes may be committed."""

    def __init__(self, message, details):
        super().__init__(message)
        self.details = details
