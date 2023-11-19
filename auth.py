import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from datetime import datetime, timedelta

class AuthHandler():
    security = HTTPBearer()
    pwd_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto")
    secret = 'SECRET'

    # This will take in a plain text password and return hash using our 'CryptoContext':
    def get_password_hash(self, password):
        return self.pwd_context.hash(password)
    
    # This takes in a plain text password and hased password and returns Boolean if matched:
    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)
    
    # This will accept the user_id as a parameter, which will be used as a subject of the token
    # We use the imported 'datetime' to set the 'expired' and 'issued out times'
    # Setting the expiration time to 5 minutes to demonstrate. Change later.
    # Then, we encode the token using our 'secret', then return:
    def encode_token(self, user_id):
        payload = {
            'exp': datetime.utcnow() + timedelta(days = 0, minutes = 30),
            'iat': datetime.utcnow(),
            'sub': user_id
        }
        return jwt.encode(
            payload,
            self.secret,
            algorithm = 'HS256'
        )
    
    # Here we take the token in as a parameter, and attempt to decode it using 'SECRET'
    # Then we return the subject for the token, the username.
    # If there are errors, HTTP exceptions will be raised
    def decode_token(self, token):
        try:
            payload = jwt.decode(token, self.secret, algorithms = ['HS256'])
            return payload['sub']
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code = 401, detail = 'Signature has expired')
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code = 401, detail = 'Invalid token')
        
    
    # We are using the HTTPBearer through dependency injection, which will be added to our routes
    # This ensures that the bearer token has been supplied in the auth header, but doesn't do anything to validate that token
    # So this will wrap that, first ensuring the token is present
    # Then if it passes that check, we will decode the token ourselves to make sure it is valid

    ### THIS IS THE FUNC TO CHECK FOR HEADER + ALSO AUTH TOKEN ###
    def auth_wrapper(self, auth: HTTPAuthorizationCredentials = Security(security)):
        return self.decode_token(auth.credentials)