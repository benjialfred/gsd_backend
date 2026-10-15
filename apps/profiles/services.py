from .models import ProfileMedia

class ProfileCompletionService:
    @staticmethod
    def calculate_completion(user_profile):
        """
        Calcule le pourcentage de complétion du profil basé sur les champs renseignés.
        Total = 100 points
        """
        score = 0
        
        # Identité et Localisation (20%)
        missing_fields = []
        if user_profile.gender: score += 5
        if user_profile.birth_date: score += 5
        if user_profile.country_code: score += 5
        else: missing_fields.append("pays")
        if getattr(user_profile, 'latitude', None): score += 5  # La ville est déduite des coordonnées
        
        # Profession et Etudes (15%)
        if user_profile.profession: score += 10
        else: missing_fields.append("profession")
        if user_profile.education_level: score += 5
        
        # Vie Spirituelle (20%)
        if user_profile.denomination: score += 10
        else: missing_fields.append("dénomination")
        if user_profile.church_attendance: score += 5
        if user_profile.spiritual_commitment: score += 5
        
        # Personnalité (via M2M relations) (15%)
        # Utiliser les résultats en mémoire si préchargés, sinon requête légère
        def _check_rel(rel):
            if hasattr(rel, '_result_cache') and rel._result_cache is not None:
                return len(rel._result_cache) > 0
            return rel.exists()

        has_languages = _check_rel(user_profile.user_languages)
        has_interests = _check_rel(user_profile.user_interests)
        has_sports = _check_rel(user_profile.user_sports)
        has_hobbies = _check_rel(user_profile.user_hobbies)
        
        if has_languages: score += 5
        if has_interests: score += 5
        if has_sports or has_hobbies: score += 5

        # Vision du mariage (10%)
        if user_profile.marriage_objectives: score += 5
        else: missing_fields.append("vision du mariage")
        if user_profile.marriage_values or user_profile.marriage_expectations: score += 5
        else: missing_fields.append("attentes du mariage")
        
        # Médias (20%)
        if hasattr(user_profile, '_prefetched_objects_cache') and 'media' in user_profile._prefetched_objects_cache:
            medias = list(user_profile.media.all())
            has_media = len(medias) > 0
            has_primary = any(getattr(m, 'is_primary', False) for m in medias)
            media_count = len(medias)
        else:
            has_media = user_profile.media.exists()
            has_primary = user_profile.media.filter(is_primary=True).exists()
            media_count = user_profile.media.count()
        
        if has_primary: score += 15
        elif has_media: score += 10
        else: missing_fields.append("photo de profil")
        
        if media_count > 1: score += 5

        next_action = None
        if missing_fields:
            next_action = f"Ajoutez votre {missing_fields[0]}"

        return {
            "completion_percentage": min(score, 100),
            "next_action": next_action
        }

