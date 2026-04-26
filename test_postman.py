import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from users.models import User

def run_postman_tests():
    print("🚀 Démarrage de la suite de tests (Simulation Postman) pour GSD...\n")
    client = APIClient()

    # 1. Test des routes publiques sans auth
    response = client.get('/api/users/')
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    print("✅ GET /api/users/ (sans token) -> 401 Unauthorized (Sécurité activée)")

    # 2. Création d'un user de test 
    user, created = User.objects.get_or_create(username='test_postman', email='test@gsd.com', role='USER')
    user.set_password('TestPass123!')
    user.save()

    # 3. Test authentification & génération JWT
    response = client.post('/api/auth/token/', {'username': 'test_postman', 'password': 'TestPass123!'})
    assert response.status_code == 200, f"Erreur de login: {response.data}"
    token = response.data['access']
    print("✅ POST /api/auth/token/ -> 200 OK (Token JWT reçu avec succès)")

    # 4. Ajout du Headers (Bearer Token)
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)

    # 5. GET Users connectés
    response = client.get('/api/users/')
    assert response.status_code == 200
    print("✅ GET /api/users/ (Token valide) -> 200 OK")

    # 6. Test Academy
    response = client.get('/api/academy/courses/')
    assert response.status_code == 200
    print("✅ GET /api/academy/courses/ -> 200 OK (Académie accessible)")

    # 7. Test Matchmaking
    response = client.get('/api/matchmaking/matches/')
    assert response.status_code == 200
    print("✅ GET /api/matchmaking/matches/ -> 200 OK (Matching accessible)")

    # 8. Test Coaching
    response = client.get('/api/coaching/profiles/')
    assert response.status_code == 200
    print("✅ GET /api/coaching/profiles/ -> 200 OK (Coaching accessible)")

    # 9. Test Marketplace (Core)
    response = client.get('/api/core/resources/')
    assert response.status_code == 200
    print("✅ GET /api/core/resources/ -> 200 OK (Marketplace/Podcasts accessible)")

    print("\n🎉 Tous les endpoints REST API répondent parfaitement sous autorisation JWT. L'API est robuste.")

if __name__ == '__main__':
    run_postman_tests()
