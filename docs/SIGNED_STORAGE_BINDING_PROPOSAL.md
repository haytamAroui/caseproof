# Proposition : filiation Storage du parcours signé

Non appliquée. Aucun changement DEV partagé, aucun utilisateur ou dossier créé.

## Modèle vérifié

La lecture de DEV du 23 novembre 2026 a confirmé les tables documents,
document_versions, _dev_journey_sources, audit_events et storage.objects.
Les fonctions existantes caseproof_dev_ingest_verified et
caseproof_dev_ingest_parsed_verified vérifient les octets, SHA-256, taille et
chemin exact avant de conserver représentation, manifeste et audit.
Le registre disposable _s2_009b_vault_intents est absent de DEV. Il ne fait
pas partie des prérequis de cette proposition.

## Delta

Appliquer SIGNED_storage_source_binding.sql avant les autres propositions
SIGNED. Cette proposition ajoute source_binding_kind et source_binding à
_m2_brief_versions et rend l'ancien vault_intent_id nullable. Les anciennes
lignes restent legacy_vault_intent avec leur ID inchangé. Elles ne deviennent
jamais implicitement des lignes vérifiées par Storage.

Une nouvelle ligne trusted_storage_source_v1 conserve l'audit d'ingestion,
le digest du snapshot, le bucket, le chemin exact, les digests original et
représentation, la taille et le type. Son ancien intent est NULL, jamais un
UUID inventé. Les deux fonctions internes ne sont pas exécutables par les
rôles clients ni par service_role. Les RPC conservent leurs contrôles de
membre et de grant actuels. Aucune politique Storage n'est élargie.

Le vérificateur interne exige le registre immuable, le bon audit et son
digest, la représentation recalculée et l'objet non archivé au chemin exact.
Cela ne prouve pas à lui seul les octets actuels : le lecteur Python signé
retélécharge et vérifie digest et taille, puis relit les métadonnées pour
refuser la révocation ou la dérive. L'ingestion parsée reste un écrivain
serveur de confiance, pas un parseur SQL ni une entrée contrôlée par le client.

Publication, relecture de contrôle, sauvegarde/relecture de revue, export,
faits et signalements refusent une filiation disparue. L'export conserve son
contrôle d'accès actuel. Aucun verdict juridique n'est ajouté.

## Historique et retour arrière

Ne pas supprimer les colonnes ou lignes après une publication. Pour arrêter
le parcours, retirer les droits d'exécution des nouveaux RPC, conserver
versions, audits, décisions, faits et signalements. La présence de colonnes
nouvelles ne transforme pas l'historique. Les anciens intents restent à
revalider séparément avant toute utilisation par ce parcours.

## Preuve et limite

Les tests utilisent PostgreSQL disposable et les propositions SQL réelles,
avec transport PostgREST, Auth et Storage simulés. Aucun intent n'est créé
par le test composé. Suppression de l'objet, mauvais chemin, contenu modifié
et révocation de grant restent des refus. Cette preuve n'est pas une
acceptation Auth/Storage/RLS réelle et ne justifie ni déploiement ni merge.
