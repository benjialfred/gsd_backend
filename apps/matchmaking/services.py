from users.models import UserProfile
from matchmaking.models import MatchPreferences

class MatchingScoreService:
    @staticmethod
    def calculate_score(current_user, candidate):
        """
        Calcule le score de compatibilité entre deux utilisateurs.
        Retourne un score global et un breakdown par catégorie.
        """
        # Dans un vrai système, on chargerait les profils complets (UserProfile) et les préférences (MatchPreferences)
        # current_profile = UserProfile.objects.get(user=current_user)
        # candidate_profile = UserProfile.objects.get(user=candidate)
        
        # Pour l'instant, algorithme simulé avec des poids basiques pour préparer la V1
        # Exemple de pondération (sur 100) :
        # - Foi (denomination, church_attendance) : 35 points
        # - Vision familiale (marriage_objectives, enfants) : 30 points
        # - Mode de vie (loisirs, sports) : 20 points
        # - Localisation (distance) : 15 points
        
        breakdown = {
            "faith": 85,
            "values": 80,
            "lifestyle": 60,
            "location": 90
        }
        
        # Score global = moyenne pondérée
        total_score = int((breakdown["faith"] * 0.35) + (breakdown["values"] * 0.30) + (breakdown["lifestyle"] * 0.20) + (breakdown["location"] * 0.15))
        
        reasons = [
            "Même dénomination chrétienne",
            "Même vision de la famille",
            "À moins de 10km de chez vous"
        ]
        
        return {
            "score": total_score,
            "breakdown": breakdown,
            "reasons": reasons,
            "explanation": {
                "strongest_factor": "Foi",
                "summary": "Vous partagez une vision spirituelle très proche."
            }
        }

class CompatibilityService:
    @staticmethod
    def format_for_frontend(score_result):
        """
        Formate le résultat du MatchingScoreService pour qu'il soit consommé directement par le Frontend
        sans que ce dernier n'ait à faire de calcul.
        """
        return {
            "compatibility": score_result["score"],
            "breakdown": score_result["breakdown"],
            "highlights": score_result["reasons"],
            "explanation": score_result["explanation"]
        }

class DiscoveryFallbackService:
    @staticmethod
    def get_fallback_candidates(current_user, limit=20):
        """
        Cold Start Engine.
        S'il n'y a pas assez de profils (ex: < 20) correspondant aux filtres stricts,
        cette méthode élargit progressivement les critères (distance, âge, intérêts)
        pour éviter la frustration de la queue vide.
        """
        from users.models import User
        # Simulation d'un élargissement:
        # 1. Ignorer la distance
        # 2. Ignorer l'âge (+/- 5 ans)
        
        # Retourne simplement des utilisateurs actifs, qui ne sont pas le current_user, 
        # et qui n'ont pas encore été swipés.
        from matchmaking.models import SwipeAction
        swiped_ids = SwipeAction.objects.filter(sender=current_user).values_list('receiver_id', flat=True)
        
        candidates = User.objects.exclude(id=current_user.id).exclude(id__in=swiped_ids)[:limit]
        return list(candidates)
