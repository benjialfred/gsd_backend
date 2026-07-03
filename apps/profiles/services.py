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
        has_languages = user_profile.user_languages.exists()
        has_interests = user_profile.user_interests.exists()
        has_sports = user_profile.user_sports.exists()
        has_hobbies = user_profile.user_hobbies.exists()
        
        if has_languages: score += 5
        if has_interests: score += 5
        if has_sports or has_hobbies: score += 5

        # Vision du mariage (10%)
        if user_profile.marriage_objectives: score += 5
        else: missing_fields.append("vision du mariage")
        if user_profile.marriage_values or user_profile.marriage_expectations: score += 5
        else: missing_fields.append("attentes du mariage")
        
        # Médias (20%)
        has_media = user_profile.media.exists()
        has_primary = user_profile.media.filter(is_primary=True).exists()
        
        if has_primary: score += 15
        elif has_media: score += 10
        else: missing_fields.append("photo de profil")
        
        if user_profile.media.count() > 1: score += 5

        next_action = None
        if missing_fields:
            next_action = f"Ajoutez votre {missing_fields[0]}"

        return {
            "completion_percentage": min(score, 100),
            "next_action": next_action
        }

