# Pilote juridique belge hors ligne

Ce volet suit le cadrage produit du 23 novembre 2026 et le choix explicite d'un corpus belge versionné livré au cabinet. Il ne remplace ni le parcours pièces/bordereau, ni les revues signées, ni la validation sur dossiers représentatifs.

## Utilisation locale

Préparer les dépendances du dépôt sur une machine connectée, puis conserver cet environnement avant de couper Internet. Aucun compte ou appel API n'est nécessaire pour ces commandes :

```sh
.venv/bin/python -m scripts.serve_offline_legal_workbench --corpus /chemin/du/pack
.venv/bin/python -m scripts.check_offline_legal_docx conclusions.docx --corpus /chemin/du/pack --output revue.zip
.venv/bin/python -m scripts.verify_offline_legal_pack revue.zip --expected-sha256 EMPREINTE_CONSERVEE_SEPAREMENT
```

Le navigateur local est servi uniquement sur `127.0.0.1`. Il accepte les octets d'un DOCX borné, pas un chemin de fichier fourni par une requête. Jeton local, origine et hôte sont contrôlés. Il réutilise le parseur DOCX conservateur du dépôt et le contrôleur déterministe des références. Les champs, révisions, contenus cachés ou autres zones non prises en charge ne deviennent pas un contrôle propre.

L'export contient `review.json` et `report.html`. Le rapport autonome ne contient ni script, ni chargement distant. Les articles et les artefacts source conservés sont dans le JSON. Le vérificateur indépendant recalcule leurs digests, l'identité du choix de corpus, les constats et la vue HTML. L'empreinte doit être conservée hors du ZIP : elle vérifie la cohérence, pas l'auteur ni l'authenticité juridique. Aucun nouveau compte, rôle ou schéma partagé n'est créé.

## Version exacte

La sélection inclut chaque clé d'article, les versions déclarées, les digests du texte et de l'artefact source, la provenance, le type de capture, les alias d'actes et la version demandée, même absente. Son digest entre dans les nouveaux snapshots de contrôle. Les anciens snapshots sans ce champ gardent leur identité historique. Une nouvelle version ou une nouvelle demande produit une nouvelle identité, sans déplacer une décision ancienne.

Une version explicitement demandée et absente produit `UNDETERMINED / requested_version_absent_from_chosen_corpus`, jamais un remplacement courant. `UNVERIFIED` reste réservé à l'article absent du corpus choisi.

Le serveur signé existant propose aussi `/dev/signed/matters/{case}/briefs/{version}/offline-legal-pack` sous les contrôles d'accès actuels. Cet export exige les artefacts source conservés et une sélection identique au run. L'export refuse un corpus partiel, des octets absents ou une dérive. Ce chemin de production de l'export reste connecté, contrairement au point d'entrée local ci-dessus.

## Sources du pilote privé, non commises

Le pilote joint au livrable privé utilise l'article 8.5, livre8 du Code civil, FR/NL, capturé depuis Justel. Il nomme sa version `justel-capture-2026-11-23-update-2024-03-29` selon l'en-tête lu, pas comme une garantie de droit applicable. Les captures lisibles complètes sont conservées, mais ne sont ni les octets HTTP originaux, ni les PDF authentiques du Moniteur. Aucun texte juridique réel ou dossier privé n'est ajouté au dépôt public.

- Justel FR : https://www.ejustice.just.fgov.be/eli/loi/2019/04/13/2019A12168/justel
- Justel NL : https://www.ejustice.just.fgov.be/eli/wet/2019/04/13/2019A12168/justel
- Conditions officielles, sectionIII : https://www.ejustice.just.fgov.be/img_2024/pdf/GebruiksvoorwaardenFR.pdf
- Repérage : https://github.com/LawCodex/be

Les conditions permettent la réutilisation des informations sauf mention contraire et recommandent source/date. Elles exigent une autorisation pour le multimédia, y compris dans les documents téléchargeables. Aucun PDF/image n'est donc redistribué sous une présomption générale. LawCodex décrit un instantané courant et exclut des textes abrogés/expirés : pas de promesse d'historique complet. La voie navigateur Justel a été arrêtée lors d'un429, sans retry périodique.

## Preuve et limites

Les six Word FR/NL ont été contrôlés à neuf après démarrage d'un nouveau processus dans un espace réseau sans route externe, puis avec création de sockets interdite pendant les contrôles. Les résultats sont PASS, FAIL et UNDETERMINED dans chaque langue. Le serveur local a ensuite accepté un Word modifié via le navigateur, produit FAIL et son ZIP avec seulement la boucle locale disponible. Après arrêt du serveur et du navigateur, un nouveau navigateur a rouvert le passage exact depuis cet export sans requête HTTP.

Cela prouve un contrôle borné sur un article réel capturé et une réouverture gelée, pas un installateur cabinet validé, l'exhaustivité du droit belge, la couverture historique, la pagination authentique du Moniteur ou une décision d'applicabilité. Les décisions locales ne sont pas des revues d'avocat authentifiées. Le produit complet et ses critères de validation restent ouverts.

## Bibliothèque locale de corpus figés

Le parcours local accepte désormais une bibliothèque append-only. Préparer un
pack ne démontre ni son authenticité ni les droits de redistribution : conserver
la provenance explicite et n'utiliser que des textes dont la réutilisation est
permise. Les conditions de cabinet ne sont pas transportées dans ce pack juridique.

```sh
uv run --locked python -m scripts.local_legal_corpus prepare --corpus /chemin/corpus --output /chemin/corpus.zip
uv run --locked python -m scripts.serve_offline_legal_workbench --corpus /chemin/corpus --library /chemin/bibliotheque
```

Dans la page locale, « Importer un pack local » ajoute un ZIP validé. Recharger
la page, puis sélectionner explicitement le corpus de la nouvelle vérification.
Chaque option montre les versions déclarées, les langues et l'empreinte complète.
Aucun alias « latest » et aucune mise à jour automatique ne sont utilisés. Le
résultat affiche aussi l'identité réellement contrôlée. L'import n'écrase pas les
packs antérieurs. Un pack modifié derrière son identité est refusé, même lors
d'une tentative de réimport. Les ZIP de revue déjà exportés restent autonomes :
ils ne consultent pas cette bibliothèque lors de leur réouverture.

La bibliothèque est locale et contrôlée par l'utilisateur du poste, pas un
service d'authentification ni une signature d'éditeur. Une sauvegarde externe est
nécessaire pour résister à la suppression des fichiers du poste. L'export reste
une tranche juridique et non la validation du parcours complet du dossier.

## Décisions locales et recontrôle

`scripts/review_offline_legal.py decide` ajoute une décision (confirmer, nuancer, rejeter, déroger) à un constat précis et écrit une nouvelle revue figée, sans modifier l'export précédent. La décision porte un libellé local non authentifié, jamais une identité d'avocat, et n'autorise aucun dépôt. Elle est liée à l'empreinte du constat : référence citée, statut, citation, texte exact de l'article et pack de corpus.

`scripts/review_offline_legal.py recheck` contrôle un Word corrigé après relecture à froid de la revue précédente. Une décision n'est conservée (origine « carried ») que si le constat est identique. Sinon elle reste visible comme décision antérieure sans effet et le nouveau constat demande une nouvelle décision. Un autre pack de corpus ne reprend jamais une décision. Les exports antérieurs à cette couche restent lisibles et vérifiables, mais refusent de recevoir des décisions.
