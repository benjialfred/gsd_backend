from django.db.models import Q
from users.models import UserProfile, User
from matchmaking.models import MatchPreferences, SwipeAction, Match

class MatchingScoreService:
    @staticmethod
    def calculate_score(current_user, candidate):
        """
        Calcule le score de compatibilité spirituelle, personnelle et géographique
        entre deux profils du Grand Salon Divin.
        """
        try:
            current_profile = UserProfile.objects.get(user=current_user)
        except UserProfile.DoesNotExist:
            current_profile = None

        try:
            candidate_profile = UserProfile.objects.get(user=candidate)
        except UserProfile.DoesNotExist:
            candidate_profile = None

        if not current_profile or not candidate_profile:
            return {
                "score": 75,
                "breakdown": {"faith": 75, "values": 70, "lifestyle": 70, "location": 80},
                "reasons": ["Profil en cours de découverte", "Cœur disposé"],
                "explanation": {"strongest_factor": "Foi", "summary": "Nouveau membre de la communauté chrétienne."}
            }

        # 1. Pilier Foi & Engagement Spirituel (35%)
        faith_score = 65
        if current_profile.denomination and candidate_profile.denomination:
            cur_denom = current_profile.denomination.strip().lower()
            cand_denom = candidate_profile.denomination.strip().lower()
            if cur_denom == cand_denom:
                faith_score = 95
            else:
                faith_score = 75
        elif current_profile.denomination or candidate_profile.denomination:
            faith_score = 70

        if current_profile.church_attendance and candidate_profile.church_attendance:
            if current_profile.church_attendance == candidate_profile.church_attendance:
                faith_score = min(100, faith_score + 15)
            else:
                faith_score = min(100, faith_score + 8)

        # 2. Pilier Valeurs & Vision du Mariage (30%)
        values_score = 70
        if current_profile.marriage_objectives and candidate_profile.marriage_objectives:
            values_score = 85
            # Bonus si mots-clés communs
            cur_obj = current_profile.marriage_objectives.lower()
            cand_obj = candidate_profile.marriage_objectives.lower()
            common_words = set(cur_obj.split()).intersection(set(cand_obj.split()))
            if len([w for w in common_words if len(w) > 4]) >= 2:
                values_score = 95

        if current_profile.education_level and candidate_profile.education_level:
            if current_profile.education_level == candidate_profile.education_level:
                values_score = min(100, values_score + 10)

        # 3. Pilier Style de Vie & Intérêts (20%)
        lifestyle_score = 65
        try:
            current_interests = set(current_profile.user_interests.values_list('interest_id', flat=True))
            candidate_interests = set(candidate_profile.user_interests.values_list('interest_id', flat=True))
            if current_interests and candidate_interests:
                common = current_interests.intersection(candidate_interests)
                if len(common) >= 3:
                    lifestyle_score = 95
                elif len(common) > 0:
                    lifestyle_score = 85
                else:
                    lifestyle_score = 65
        except Exception:
            lifestyle_score = 70

        # 4. Pilier Localisation & Proximité (15%)
        location_score = 60
        if current_profile.city and candidate_profile.city:
            if current_profile.city.strip().lower() == candidate_profile.city.strip().lower():
                location_score = 98
            else:
                location_score = 60
        elif current_profile.country_code and candidate_profile.country_code:
            if current_profile.country_code.strip().upper() == candidate_profile.country_code.strip().upper():
                location_score = 80
            else:
                location_score = 55

        breakdown = {
            "faith": min(100, faith_score),
            "values": min(100, values_score),
            "lifestyle": min(100, lifestyle_score),
            "location": min(100, location_score)
        }

        total_score = int(
            (breakdown["faith"] * 0.35) +
            (breakdown["values"] * 0.30) +
            (breakdown["lifestyle"] * 0.20) +
            (breakdown["location"] * 0.15)
        )
        total_score = max(65, min(99, total_score))

        # Points forts inspirants
        reasons = []
        if breakdown["faith"] >= 80:
            denom_label = current_profile.denomination.replace('_', ' ').capitalize() if current_profile.denomination else "Chrétienne"
            reasons.append(f"Sensibilité spirituelle ({denom_label})")
        if breakdown["location"] >= 85:
            reasons.append(f"Proximité ({candidate_profile.city or 'Même région'})")
        if breakdown["values"] >= 80:
            reasons.append("Vision partagée du mariage chrétien")
        if breakdown["lifestyle"] >= 80:
            reasons.append("Affinité dans les centres d'intérêt")

        if not reasons:
            reasons.append("Profils aux valeurs complémentaires")
            reasons.append("Dévotion chrétienne sincère")

        factor_names = {"faith": "Foi", "values": "Vision du Mariage", "lifestyle": "Style de vie", "location": "Proximité"}
        strongest = max(breakdown.items(), key=lambda x: x[1])

        return {
            "score": total_score,
            "breakdown": breakdown,
            "reasons": reasons[:3],
            "explanation": {
                "strongest_factor": factor_names.get(strongest[0], "Foi"),
                "summary": f"Forte convergence spirituelle et humaine détectée autour de la {factor_names.get(strongest[0], 'Foi').lower()}."
            }
        }

class CompatibilityService:
    @staticmethod
    def format_for_frontend(score_result):
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
        Génère les candidats idéaux pour l'utilisateur connecté :
        1. Filtre par sexe complémentaire (Homme <-> Femme).
        2. Exclut les profils déjà swipés (Likes/Pass) ou déjà matchés.
        3. Priorise les profils ayant complété leur profil avec photos.
        """
        # IDs à exclure
        swiped_ids = set(SwipeAction.objects.filter(sender=current_user).values_list('receiver_id', flat=True))
        matched_u1 = set(Match.objects.filter(user1=current_user).values_list('user2_id', flat=True))
        matched_u2 = set(Match.objects.filter(user2=current_user).values_list('user1_id', flat=True))
        excluded_ids = swiped_ids | matched_u1 | matched_u2 | {current_user.id}

        current_profile = getattr(current_user, 'profile', None)
        target_gender = None
        if current_profile and current_profile.gender:
            target_gender = 'F' if current_profile.gender == 'M' else 'M'

        candidates = []

        # 1. Candidats du genre ciblé ayant complété l'onboarding
        if target_gender:
            qs_completed = User.objects.filter(
                profile__gender=target_gender,
                profile__onboarding_completed=True,
                is_active=True
            ).exclude(id__in=excluded_ids).select_related('profile')
            candidates.extend(list(qs_completed[:limit]))

        # 2. Si moins que limit, candidats du genre ciblé (en cours de finalisation)
        if target_gender and len(candidates) < limit:
            already_ids = excluded_ids | {u.id for u in candidates}
            qs_gender = User.objects.filter(
                profile__gender=target_gender,
                is_active=True
            ).exclude(id__in=already_ids).select_related('profile')
            candidates.extend(list(qs_gender[:(limit - len(candidates))]))

        # 3. File de secours si la base est encore très restreinte (sans restriction de genre si aucun profil opposé)
        if len(candidates) < limit:
            already_ids = excluded_ids | {u.id for u in candidates}
            qs_fallback = User.objects.filter(
                is_active=True
            ).exclude(id__in=already_ids).select_related('profile')
            candidates.extend(list(qs_fallback[:(limit - len(candidates))]))

        return candidates[:limit]
