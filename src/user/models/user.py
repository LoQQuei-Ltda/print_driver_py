class User:
    """Modelo de usuário"""

    def __init__(self, user_data=None):
        """Inicializa o modelo"""
        self.user_data = user_data or {}
        self.id = self.user_data.get("id")
        self.name = self.user_data.get("name")
        self.email = self.user_data.get("email")
        self.profile = self.user_data.get("profile")
        self.picture = self.user_data.get("picture")
    
    @property
    def initial(self):
        """Retorna a inicial do usuário"""
        return self.name[0].upper() if self.name else "U"
    
    @property
    def get_profile(self):
        """Retorna o perfil do usuário"""
        if self.profile.lower() == "admin":
            return "Administrador"
        elif self.profile.lower() == "manager":
            return "Gerente"
        else:
            return "Usuário"
