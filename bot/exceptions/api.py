
class NeedReLoginError(Exception):
    pass

class NeedRefreshTokenError(Exception):
    pass

class InvalidUsernameError(Exception):
    pass

class AuthError(Exception):
    pass

class AlreadyConnectError(Exception):
    pass

class UsernameNotAvailableError(Exception):
    pass