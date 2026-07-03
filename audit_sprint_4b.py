import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps'))
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from users.models import User, UserProfile
from matchmaking.models import Match, MatchCandidate, SwipeAction, SuggestionStatus
from analytics.models import UserJourneyEvent
from django.core.cache import cache
from django.test import Client
import json
from rest_framework_simplejwt.tokens import RefreshToken

# --- Mock Cache for local test without Redis ---
class MockCache:
    def __init__(self):
        self.data = {}
    def get(self, key, default=None):
        return self.data.get(key, default)
    def set(self, key, value, timeout=None):
        self.data[key] = value
    def delete(self, key):
        self.data.pop(key, None)
    def clear(self):
        self.data.clear()

mock_cache = MockCache()

# Replace cache usages
import matchmaking.views
matchmaking.views.cache = mock_cache
# -----------------------------------------------

def print_section(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

def setup_test_data():
    # Nettoyer
    User.objects.all().delete()
    mock_cache.clear()
    
    # Créer le test user
    user1 = User.objects.create_user(username='john', email='john@test.com', password='password', first_name='John')
    UserProfile.objects.create(user=user1, kyc_status='APPROVED')
    
    # Créer des candidats
    for i in range(5):
        c = User.objects.create_user(username=f'candidate_{i}', email=f'c{i}@test.com', password='password', first_name=f'Candidate {i}')
        UserProfile.objects.create(user=c, kyc_status='APPROVED')
        
    return user1

def run_audit():
    user = setup_test_data()
    refresh = RefreshToken.for_user(user)
    token = str(refresh.access_token)
    
    client = Client()
    headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
    
    print_section("1. Contract Audit : GET /api/matches/suggestions/")
    
    response = client.get('/api/matchmaking/suggestions/', **headers)
    print("Status Code:", response.status_code)
    data = response.json()
    print("Payload retourné :")
    print(json.dumps(data, indent=2))
    
    if data.get('suggestions'):
        suggestion = data['suggestions'][0]
        candidate_id = suggestion['candidate_id']
        suggestion_id = suggestion['id']
    else:
        print("Aucune suggestion retournée.")
        return
        
    print_section("2. Redis Queue Audit")
    
    queue_key = f"user_match_queue:{user.id}"
    cached = mock_cache.get(queue_key)
    print(f"Redis Queue exists? {cached is not None}")
    if cached:
        print(f"Items in queue: {len(cached)}")
        
    # Corrompre la file (simuler expiration)
    print("\nSimulation expiration de la file...")
    mock_cache.delete(queue_key)
    cached = mock_cache.get(queue_key)
    print(f"Redis Queue exists after delete? {cached is not None}")
    
    response2 = client.get('/api/matchmaking/suggestions/', **headers)
    print("Nouvel appel à l'API après expiration de la file. Status Code:", response2.status_code)
    cached2 = mock_cache.get(queue_key)
    print(f"Redis Queue rebuilt? {cached2 is not None}")
    
    print_section("3. Match Atomicity Audit")
    # Simulation d'un Like mutuel
    # Candidat like User en arrière-plan
    c_user = User.objects.get(id=candidate_id)
    SwipeAction.objects.create(sender=c_user, receiver=user, action='LIKE')
    
    print("Candidate a déjà liké le User.")
    print("Envoi du LIKE du User vers le Candidat...")
    
    res_action = client.post('/api/matchmaking/action/', {
        "target_user_id": candidate_id,
        "action": "LIKE"
    }, content_type="application/json", **headers)
    
    print("Action Response:", res_action.status_code)
    print(json.dumps(res_action.json(), indent=2))
    
    # Vérifications Base de données
    match_created = Match.objects.filter(user1=user, user2=c_user).exists()
    print(f"Match créé en DB ? {match_created}")
    
    mc_status = MatchCandidate.objects.get(id=suggestion_id).status
    print(f"MatchCandidate status mis à jour ? {mc_status == SuggestionStatus.MATCHED} ({mc_status})")
    
    events = UserJourneyEvent.objects.filter(user=user).values_list('event_type', flat=True)
    print(f"Analytics Events enregistrés pour le user : {list(events)}")
    
    print_section("4. Anti-Burn Audit")
    print("Simulation de 30 swipes...")
    # On a déjà fait 1 swipe (plus haut), on en fait 29 autres (dummy)
    dummy_users = [User(username=f'dummy_{i}', email=f'dummy{i}@test.com', password='password') for i in range(29)]
    User.objects.bulk_create(dummy_users)
    
    for dummy_c in dummy_users:
        SwipeAction.objects.create(sender=user, receiver=dummy_c, action='PASS')
        
    res_limit = client.get('/api/matchmaking/suggestions/', **headers)
    print("Appel API Suggestions après limite atteinte:")
    print("Status Code:", res_limit.status_code)
    print(json.dumps(res_limit.json(), indent=2))

    print_section("5. Analytics Audit")
    print("Résumé des événements :")
    all_events = UserJourneyEvent.objects.all().values('user__username', 'event_type')
    for e in all_events:
        print(f" - {e['user__username']} : {e['event_type']}")
        
if __name__ == "__main__":
    run_audit()
