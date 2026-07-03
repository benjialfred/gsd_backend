# Guide de Démarrage Développeur - GSD

Ce document explique comment lancer l'infrastructure locale pour le développement du projet **Le Grand Salon Divin**.

---

## 1. Prérequis
* Docker & Docker Compose
* Python 3.10+
* Node.js 18+

---

## 2. Démarrage de Redis (Docker)
L'infrastructure temps réel (Django Channels/WebSockets) nécessite un serveur Redis local.

Lancer le conteneur en arrière-plan :
```bash
docker compose up -d
```

Pour vérifier que le conteneur tourne correctement :
```bash
docker ps
```

---

## 3. Démarrage du Backend (Django)
1. Activez le venv Python.
2. Assurez-vous d'avoir configuré le fichier `.env.development`.
3. Lancez les migrations et démarrez le serveur :
```bash
python manage.py migrate
python manage.py runserver
```

---

## 4. Démarrage du Frontend (React)
1. Installez les dépendances :
```bash
npm install
```
2. Lancez le serveur de développement :
```bash
npm run dev
```
Le serveur React tournera sur `http://localhost:3000/`.
