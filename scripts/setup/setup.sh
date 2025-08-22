#!/bin/bash

echo "🚀 Setup CIP Immobiliare - Flask + PostgreSQL"

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 non trovato. Installa Python 3.8+"
    exit 1
fi

# Verifica PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL non trovato. Installa PostgreSQL"
    exit 1
fi

# Verifica createdb
if ! command -v createdb &> /dev/null; then
    echo "❌ createdb non trovato. Verifica installazione PostgreSQL"
    exit 1
fi

echo "✅ Dipendenze di sistema verificate"

# Ambiente virtuale
if [ ! -d ".venv" ]; then
    echo "📦 Creazione ambiente virtuale..."
    python3 -m venv .venv
fi

echo "🔧 Attivazione ambiente virtuale..."
source .venv/bin/activate

echo "📚 Installazione dipendenze Python..."
pip install -r requirements.txt

# Configurazione ambiente
if [ ! -f ".env" ]; then
    echo "⚙️  Creazione file .env..."
    cp config/env/env.example .env
    echo "📝 Modifica .env con le tue credenziali PostgreSQL"
else
    echo "✅ File .env già esistente"
fi

# Database
echo "🗄️  Creazione database..."
if createdb cip 2>/dev/null; then
    echo "✅ Database 'cip' creato"
else
    echo "ℹ️  Database 'cip' già esistente"
fi

echo "📊 Applicazione schema database..."
psql -d cip -f config/database/schema.sql

echo "🎉 Setup completato!"
echo ""
echo "Per avviare l'applicazione:"
echo "1. Modifica .env con le tue credenziali"
echo "2. Attiva l'ambiente virtuale: source .venv/bin/activate"
echo "3. Avvia: export FLASK_APP=admin.py && flask run --debug"
echo ""
echo "🌐 L'applicazione sarà disponibile su: http://localhost:5000"
