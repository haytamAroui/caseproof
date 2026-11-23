# Rejouer la suite d'acceptation jetable en local

Ordre et prérequis pour reproduire la suite `m1-m2-integrated-disposable-ci`
hors GitHub Actions, sans échecs de base connus. Base : PostgreSQL local
loopback uniquement, base dédiée `caseproof_s2_ci`, utilisateur `postgres`,
mot de passe fixture `caseproof_ephemeral_ci`. Aucune credential Supabase.

## Prérequis du cluster (pièges réels)

1. **Encodage UTF8 obligatoire.** Un cluster ou une base en SQL_ASCII fait
   échouer `verify_vault_integration` et les suites M2 : psycopg renvoie alors
   `bytes` pour les colonnes `text`, et la comparaison du reçu du ledger
   (`state != "pending"`) échoue. Créer la base avec
   `create database caseproof_s2_ci encoding 'UTF8' template template0`
   (l'image CI `postgres:17` est UTF8 par défaut ; un `initdb` sous locale
   C/POSIX ne l'est pas).
2. **Rôles globaux au cluster.** `anon` et `authenticated` sont créés par
   S2-002 et partagés par toutes les bases du cluster. Après un `drop database`
   ou `drop schema`, les supprimer (`drop role if exists anon, authenticated`)
   avant de relancer, sinon S2-002 échoue avec « role already exists ».
3. **Port 5432 épinglé.** Les scripts refusent tout autre port.
4. **Opt-in S2-007** : `CASEPROOF_S2_007_SYNTHETIC=YES` est requis.

## Ordre cumulatif (même base, sans réinitialisation entre les scripts)

```
CASEPROOF_DISPOSABLE_DB=YES PGHOST=127.0.0.1 PGPORT=5432 \
PGDATABASE=caseproof_s2_ci PGUSER=postgres PGPASSWORD=caseproof_ephemeral_ci

python -m scripts.verify_s2_002_database
python -m scripts.verify_m1_disposable_exhibits
CASEPROOF_S2_007_SYNTHETIC=YES python -m scripts.verify_s2_007_disposable_tenancy
python -m scripts.verify_s2_004_database
python -m scripts.verify_s2_008a_database
python -m scripts.verify_s2_008a3_reader
python -m scripts.verify_s2_009b_database
python -m scripts.verify_vault_integration
python -m scripts.verify_m2_disposable_runs
python -m scripts.verify_m2_brief_graph
python -m scripts.verify_m2_private_check_composition
python -m scripts.verify_m2_disposable_corrections
python -m scripts.verify_m1_private_rls
```

Vérifié vert de bout en bout sur PostgreSQL 16 local (binaires pgserver),
le 2026-11-23, avec le contrat d'étape S2-009b aligné sur `_ALLOWED_MIME`
(DOCX inclus). Les réserves d'identité des scripts (identités synthétiques,
pas de session Auth signée réelle) restent affichées par S2-007 et
M1_PRIVATE_RLS et ne sont pas des échecs.
