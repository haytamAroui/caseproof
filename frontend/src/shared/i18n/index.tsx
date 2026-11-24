import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type Locale = 'fr' | 'nl' | 'en';
export type ResultCategory =
  'correspondance' | 'ecart' | 'impossible' | 'appreciation';

const SUPPORTED: readonly Locale[] = ['fr', 'nl', 'en'];

export function detectInitialLocale(
  search: string = typeof window !== 'undefined' ? window.location.search : '',
  browserLang: string = typeof navigator !== 'undefined'
    ? navigator.language
    : 'en',
): Locale {
  const param = new URLSearchParams(search).get('lang')?.toLowerCase();
  if (param === 'fr' || param === 'nl' || param === 'en') return param;
  const base = browserLang.toLowerCase().split('-')[0];
  if (base === 'fr') return 'fr';
  if (base === 'nl') return 'nl';
  return 'en';
}

const MESSAGES: Record<Locale, Record<string, string>> = {
  en: {
    skip: 'Skip to content',
    brandSubtitle: 'Evidence workspace',
    endSession: 'End session',
    languageLabel: 'Workspace language',
    navMatter: 'Matter',
    navVerification: 'Verification',
    navLegal: 'Legal articles',
    navExport: 'Export',
    footer: 'Development foundation · Synthetic acceptance only',
    signInEyebrow: 'Private evidence review',
    signInTitle: 'Connect your workspace session',
    signInLead:
      'Sign in to your workspace. Your account must have access to each matter.',
    reviewHeading: 'Review the evidence',
    findingsHeading: 'Findings',
    filterAttention: 'Needs attention',
    filterAll: 'Show all',
    searchPlaceholder: 'Reference text',
    searchLabel: 'Search reference text (this session only)',
    selectedReference: 'Selected reference',
    draftHeading: 'Draft',
    sourceEvidenceHeading: 'Source evidence',
    splitView: 'Split view',
    draftFocus: 'Draft focus',
    sourceFocus: 'Source focus',
    sourcePixelsHeading: 'Preserved source pixels',
    scopeLimits: 'Scope & limits',
    refPdfPage: 'Reference PDF page',
    printedPage: 'Printed page',
    bundlePage: 'Bundle page',
    returnToRefPage: 'Return to reference page',
    findOnPage: 'Find text on this page',
    findOnPagePlaceholder: 'Find text on page…',
    clearPageSearch: 'Clear page search',
    hideBoxes: 'Hide navigation boxes',
    showBoxes: 'Show navigation boxes',
    sourcePageRendered: 'Source page rendered.',
    renderingSourcePage: 'Rendering source page…',
    legalTitle: 'Cited legal articles',
    legalBack: 'Back to preserved reports',
    legalAll: 'All detected',
    legalCompare: 'Compare with stored article',
    legalHide: 'Hide stored article',
    legalDraft: 'Your draft',
    legalStored: 'Stored article text',
    legalRulesHeading: 'Lawyer-defined rules on declared facts',
    legalCoverage: 'Coverage & limits',
    legalReviewTitle: 'Reviewer statement',
    legalReviewLead:
      "A person's statement about this finding. It does not change the status above and does not approve filing.",
    legalStatementLabel: 'Statement',
    legalReasonLabel: 'Reason (required)',
    legalRecordBtn: 'Record statement',
    dimIdentity: 'Identity',
    dimPageMapping: 'Page mapping',
    dimFidelity: 'Fidelity',
    dimHumanSupport: 'Human support',
    catCorrespondance: 'Literal match',
    catEcart: 'Mismatch',
    catImpossible: 'Check impossible',
    catAppreciation: 'Appraisal required',
    legalPass: 'Found in the stored text',
    legalFail: 'Does not match the stored text',
    legalUnverified: 'Not in the chosen corpus',
    legalUndetermined: 'Cannot be decided',
    journeyCaption: 'Dossier workflow',
    journeyNote: 'Navigation does not establish completion',
    step1: 'Matter & intake',
    step2: 'Confirm inventory',
    step3: 'Verification & coverage',
    step4: 'Evidence review',
    step5: 'Correction & recheck',
    step6: 'Release & export',
    step7: 'Historical reopening',
    linkExports: 'Reviewed exports and historical downloads',
    linkEditDocx: 'Edit current DOCX candidate (not committed)',
    linkReconfirmInv: 'Reconfirm inventory and page mappings',
    reviewSubtitle:
      'Each result describes a separate check. Human judgment remains separate.',
    snapshotCurrentNotice:
      'Current snapshot inspection. Human decisions remain separate from source rendering.',
    snapshotHistoricalNotice:
      'Historical snapshot. Current permissions were checked again, but this report cannot be reviewed, corrected, rechecked or exported as current. Source availability is checked separately.',
    queueAttentionCount: 'need attention out of',
    queueDetectedSuffix: 'detected references. Review coverage separately.',
    queueFilteredSuffix: 'references match the current filter and search.',
    queueShortcutHint:
      'When a reference button is focused, press J/K for next/previous or Space to inspect it. No decision is saved by a shortcut.',
    queueNoFlag: 'No machine discrepancy flagged',
    readingSplitNote:
      'Three-panel review: the preserved draft and original source remain separate. Drag the divider or use arrow keys.',
    readingDraftNote:
      'Draft focus. Source evidence is hidden, not verified or discarded.',
    readingSourceNote:
      'Source focus. Preserved original pixels remain the inspection authority.',
    sourceWidthLabel: 'Source panel width:',
    restoreSourceWidth: 'Restore 400px source',
    draftPaneSubtitle: 'Preserved DOCX · extracted context',
    originalPdfTag: 'original PDF',
    draftContextTitle: 'Preserved DOCX reference context',
    draftContextNotice:
      'Bounded extracted plain text, not Word pagination or a safe editable location. No document mutation is performed.',
    draftContextLoading: 'Loading authorized draft context…',
    draftContextUnavailable:
      'Draft context unavailable; do not infer the reference anchor.',
    draftAnchorUnsupported:
      'Draft anchor unsupported or ambiguous. Do not guess the first matching paragraph.',
    quoteCardTitle: 'Quotation and derived source text',
    noGuardedTermNotice:
      'This frozen report has no guarded-term review. Inspect the preserved source and surrounding context prior to making a semantic decision.',
    quoteCompareHint:
      'Compare this text with the preserved source pixels. A text match is not a finding of legal support.',
    quoteInDraftHeading: 'Quotation in draft',
    quoteUnavailable: 'No supported quotation is available in this report.',
    extractedSourceHeading: 'Extracted source text',
    extractedSourceUnavailable:
      'Extracted source text is unavailable or unsupported. Inspect the preserved pixels.',
    translationNotice:
      'Translation requires human review; the texts may be in different languages.',
    notSupplied: 'Not supplied',
    pdfPageLabel: 'PDF page',
    ofWord: 'of',
    zoomWord: 'Zoom',
    refPageMappingLabel: 'Reference page mapping:',
    sourceScopeBody:
      'Source inspection does not change identity, page mapping, fidelity or human support. Extracted text and search boxes below are derived navigation aids.',
    legalCorpusPrefix: 'Chosen corpus:',
    legalCorpusArticles: 'articles, pack',
    legalCorpusDisclaimer:
      'No applicability or currency claim is made about it.',
    legalNoCorpus:
      'No corpus is chosen for this matter. No article can be found, so nothing is marked as found.',
    legalReasonLabelPrefix: 'Reason:',
    legalClaimSupportUnassessed: 'Claim support: not assessed.',
    legalNoArticleStored: 'No stored article for this citation.',
    legalNoRulesEvaluated:
      'No lawyer-defined rule was evaluated for this run. Nothing here is a legal conclusion.',
    legalChoiceConfirm: 'I confirm this finding exists as shown',
    legalChoiceDismiss: 'I dismiss this finding',
    legalChoiceNeedsInfo: 'More information is needed',
    legalLedgerUnavailable:
      'The review ledger is unavailable. Nothing can be recorded.',
    legalLedgerStale:
      'The ledger is bound to a different check. Reload before deciding.',
  },
  fr: {
    skip: 'Aller au contenu',
    brandSubtitle: 'Couche de contrôle avant dépôt',
    endSession: 'Fermer la session',
    languageLabel: 'Langue de l’interface',
    navMatter: 'Dossier',
    navVerification: 'Contrôle pièces',
    navLegal: 'Articles cités',
    navExport: 'Export',
    footer: 'Socle de développement · Recette synthétique uniquement',
    signInEyebrow: 'Revue confidentielle des preuves',
    signInTitle: 'Ouvrir votre session de travail',
    signInLead:
      'Connectez-vous à votre espace. Votre compte doit disposer des droits sur chaque dossier.',
    reviewHeading: 'Contrôle des pièces et citations',
    findingsHeading: 'Constats',
    filterAttention: 'À traiter',
    filterAll: 'Tout afficher',
    searchPlaceholder: 'Rechercher un renvoi',
    searchLabel: 'Filtrer les renvois (session en cours)',
    selectedReference: 'Constat sélectionné',
    draftHeading: 'Conclusions',
    sourceEvidenceHeading: 'Pièce originale',
    splitView: 'Vue partagée',
    draftFocus: 'Conclusions',
    sourceFocus: 'Source PDF',
    sourcePixelsHeading: 'Page originale conservée',
    scopeLimits: 'Périmètre et limites',
    refPdfPage: 'Page PDF',
    printedPage: 'Page imprimée',
    bundlePage: 'Page dossier',
    returnToRefPage: 'Revenir à la page citée',
    findOnPage: 'Rechercher sur cette page',
    findOnPagePlaceholder: 'Rechercher sur la page…',
    clearPageSearch: 'Effacer la recherche',
    hideBoxes: 'Masquer les repères',
    showBoxes: 'Afficher les repères',
    sourcePageRendered: 'Page originale affichée.',
    renderingSourcePage: 'Chargement de la page originale…',
    legalTitle: 'Articles du corpus juridique choisi',
    legalBack: 'Retour aux rapports conservés',
    legalAll: 'Tous les constats',
    legalCompare: 'Comparer avec l’article conservé',
    legalHide: 'Masquer l’article conservé',
    legalDraft: 'Extrait des conclusions',
    legalStored: 'Texte conservé dans le corpus',
    legalRulesHeading: 'Conditions définies par l’avocat',
    legalCoverage: 'Couverture et limites d’analyse',
    legalReviewTitle: 'Décision de l’avocat',
    legalReviewLead:
      'Appréciation humaine liée à ce constat. Elle ne modifie pas le constat technique et n’autorise pas automatiquement le dépôt.',
    legalStatementLabel: 'Décision',
    legalReasonLabel: 'Motif (obligatoire)',
    legalRecordBtn: 'Enregistrer la décision',
    dimIdentity: 'Identité pièce',
    dimPageMapping: 'Pagination',
    dimFidelity: 'Fidélité citation',
    dimHumanSupport: 'Décision humaine',
    catCorrespondance: 'Correspondance constatée',
    catEcart: 'Écart constaté',
    catImpossible: 'Contrôle impossible',
    catAppreciation: 'Appréciation requise',
    legalPass: 'Correspondance constatée',
    legalFail: 'Écart constaté',
    legalUnverified: 'Contrôle impossible',
    legalUndetermined: 'Appréciation requise',
    journeyCaption: 'Parcours du dossier',
    journeyNote: 'La navigation n’établit pas l’achèvement de la revue',
    step1: 'Dossier et import',
    step2: 'Confirmer le bordereau',
    step3: 'Contrôle et couverture',
    step4: 'Revue des preuves',
    step5: 'Correction et recontrôle',
    step6: 'Clôture et export',
    step7: 'Réouverture historique',
    linkExports: 'Exports revus et téléchargements historiques',
    linkEditDocx: 'Éditer le candidat DOCX courant (non figé)',
    linkReconfirmInv: 'Reconfirmer le bordereau et la pagination',
    reviewSubtitle:
      'Chaque constat décrit un contrôle distinct. L’appréciation de l’avocat reste séparée.',
    snapshotCurrentNotice:
      'Inspection de la version courante. Les décisions de l’avocat restent distinctes du rendu de la source.',
    snapshotHistoricalNotice:
      'Version historique en lecture seule. Les droits courants ont été vérifiés, mais cette version ne peut être modifiée ni exportée comme courante.',
    queueAttentionCount: 'constat(s) à examiner sur',
    queueDetectedSuffix:
      'renvois détectés. Consulter la couverture séparément.',
    queueFilteredSuffix: 'renvoi(s) affiché(s) dans ce filtre.',
    queueShortcutHint:
      'Sur un renvoi sélectionné : J/K pour suivant/précédent, Espace pour inspecter. Aucun raccourci n’enregistre de décision.',
    queueNoFlag: 'Aucun écart machine signalé',
    readingSplitNote:
      'Revue à trois volets : conclusions conservées et pièce originale restent séparées. Faites glisser le séparateur ou utilisez les flèches.',
    readingDraftNote:
      'Vue conclusions. La pièce originale est masquée, pas vérifiée ni écartée.',
    readingSourceNote:
      'Vue source. La page originale conservée fait foi pour l’inspection.',
    sourceWidthLabel: 'Largeur du volet source :',
    restoreSourceWidth: 'Réinitialiser (400px)',
    draftPaneSubtitle: 'DOCX conservé · contexte extrait',
    originalPdfTag: 'PDF original',
    draftContextTitle: 'Contexte conservé dans les conclusions DOCX',
    draftContextNotice:
      'Texte brut extrait et borné, sans pagination Word ni modification du document original.',
    draftContextLoading: 'Chargement du contexte des conclusions…',
    draftContextUnavailable:
      'Contexte des conclusions indisponible ; ne pas présumer l’emplacement exact.',
    draftAnchorUnsupported:
      'Ancrage ambigu ou non pris en charge dans le Word. Ne pas présumer le premier paragraphe correspondant.',
    quoteCardTitle: 'Citation et texte dérivé de la source',
    noGuardedTermNotice:
      'Ce rapport figé ne comporte pas de contrôle de termes réservés. Inspectez la pièce originale et son contexte avant de décider.',
    quoteCompareHint:
      'Comparez ce texte avec la page originale affichée à droite. Une correspondance littérale ne vaut pas validation juridique.',
    quoteInDraftHeading: 'Citation dans les conclusions',
    quoteUnavailable: 'Aucune citation prise en charge dans ce rapport.',
    extractedSourceHeading: 'Texte extrait de la source',
    extractedSourceUnavailable:
      'Texte extrait indisponible ou non pris en charge. Inspectez la page originale.',
    translationNotice:
      'Traduction à apprécier par l’avocat : les conclusions et la pièce sont dans des langues différentes.',
    notSupplied: 'Non renseignée',
    pdfPageLabel: 'Page PDF',
    ofWord: 'sur',
    zoomWord: 'Zoom',
    refPageMappingLabel: 'Pagination :',
    sourceScopeBody:
      'L’inspection de la source ne modifie ni l’identité, ni la pagination, ni la fidélité, ni la décision humaine. Le texte extrait et les repères sont des aides de navigation.',
    legalCorpusPrefix: 'Corpus choisi :',
    legalCorpusArticles: 'articles, pack',
    legalCorpusDisclaimer:
      'Aucune garantie d’applicabilité ni de vigueur actuelle n’est émise.',
    legalNoCorpus:
      'Aucun corpus n’est sélectionné pour ce dossier. Aucun article ne peut être vérifié.',
    legalReasonLabelPrefix: 'Motif :',
    legalClaimSupportUnassessed: 'Portée juridique : à apprécier par l’avocat.',
    legalNoArticleStored: 'Aucun article conservé pour ce renvoi.',
    legalNoRulesEvaluated:
      'Aucune condition d’avocat n’a été évaluée pour ce contrôle.',
    legalChoiceConfirm: 'Je confirme ce constat tel qu’affiché',
    legalChoiceDismiss: 'J’écarte ce constat',
    legalChoiceNeedsInfo: 'Complément d’information nécessaire',
    legalLedgerUnavailable:
      'Le registre signé est indisponible. Aucune décision ne peut être enregistrée.',
    legalLedgerStale:
      'Le registre est lié à un autre contrôle. Rechargez avant de décider.',
  },
  nl: {
    skip: 'Naar inhoud',
    brandSubtitle: 'Controlelaag vóór neerlegging',
    endSession: 'Sessie beëindigen',
    languageLabel: 'Taal van de werkruimte',
    navMatter: 'Dossier',
    navVerification: 'Stukkencontrole',
    navLegal: 'Geciteerde artikelen',
    navExport: 'Export',
    footer: 'Ontwikkelingsbasis · Uitsluitend synthetische validatie',
    signInEyebrow: 'Vertrouwelijke bewijsbeoordeling',
    signInTitle: 'Werkruimtesessie openen',
    signInLead:
      'Meld u aan bij uw werkruimte. Uw account moet toegang hebben tot elk dossier.',
    reviewHeading: 'Controle van stukken en citaten',
    findingsHeading: 'Vaststellingen',
    filterAttention: 'Te behandelen',
    filterAll: 'Alles tonen',
    searchPlaceholder: 'Zoek verwijzing',
    searchLabel: 'Verwijzingen filteren (huidige sessie)',
    selectedReference: 'Geselecteerde vaststelling',
    draftHeading: 'Conclusies',
    sourceEvidenceHeading: 'Oorspronkelijk stuk',
    splitView: 'Gesplitst',
    draftFocus: 'Conclusies',
    sourceFocus: 'Bron-PDF',
    sourcePixelsHeading: 'Bewaarde oorspronkelijke pagina',
    scopeLimits: 'Reikwijdte en grenzen',
    refPdfPage: 'PDF-pagina',
    printedPage: 'Gedrukte pagina',
    bundlePage: 'Bundelpagina',
    returnToRefPage: 'Terug naar geciteerde pagina',
    findOnPage: 'Zoeken op deze pagina',
    findOnPagePlaceholder: 'Zoek op pagina…',
    clearPageSearch: 'Zoekopdracht wissen',
    hideBoxes: 'Kaders verbergen',
    showBoxes: 'Kaders tonen',
    sourcePageRendered: 'Bronpagina weergegeven.',
    renderingSourcePage: 'Bronpagina wordt geladen…',
    legalTitle: 'Geciteerde artikelen uit het gekozen corpus',
    legalBack: 'Terug naar bewaarde rapporten',
    legalAll: 'Alle vaststellingen',
    legalCompare: 'Vergelijken met bewaard artikel',
    legalHide: 'Bewaard artikel verbergen',
    legalDraft: 'Fragment uit conclusies',
    legalStored: 'Bewaarde tekst in het corpus',
    legalRulesHeading: 'Door de advocaat bepaalde voorwaarden',
    legalCoverage: 'Dekking en analysebeperkingen',
    legalReviewTitle: 'Beslissing van de advocaat',
    legalReviewLead:
      'Menselijke beoordeling gekoppeld aan deze vaststelling. Zij wijzigt de technische vaststelling niet en keurt neerlegging niet goed.',
    legalStatementLabel: 'Beslissing',
    legalReasonLabel: 'Motivering (verplicht)',
    legalRecordBtn: 'Beslissing vastleggen',
    dimIdentity: 'Identiteit stuk',
    dimPageMapping: 'Paginering',
    dimFidelity: 'Citaatgetrouwheid',
    dimHumanSupport: 'Menselijke beoordeling',
    catCorrespondance: 'Overeenstemming vastgesteld',
    catEcart: 'Afwijking vastgesteld',
    catImpossible: 'Controle onmogelijk',
    catAppreciation: 'Beoordeling vereist',
    legalPass: 'Overeenstemming vastgesteld',
    legalFail: 'Afwijking vastgesteld',
    legalUnverified: 'Controle onmogelijk',
    legalUndetermined: 'Beoordeling vereist',
    journeyCaption: 'Dossiertraject',
    journeyNote: 'Navigatie bevestigt geen volledige beoordeling',
    step1: 'Dossier en invoer',
    step2: 'Inventaris bevestigen',
    step3: 'Controle en dekking',
    step4: 'Bewijsbeoordeling',
    step5: 'Correctie en hercontrole',
    step6: 'Afsluiting en export',
    step7: 'Historisch heropenen',
    linkExports: 'Beoordeelde exports en historische downloads',
    linkEditDocx: 'Huidige DOCX-kandidaat bewerken (niet vastgelegd)',
    linkReconfirmInv: 'Inventaris en paginering opnieuw bevestigen',
    reviewSubtitle:
      'Elk resultaat beschrijft een afzonderlijke controle. Het oordeel van de advocaat blijft gescheiden.',
    snapshotCurrentNotice:
      'Inspectie van de huidige versie. Beslissingen van de advocaat blijven gescheiden van de bronweergave.',
    snapshotHistoricalNotice:
      'Historische versie (alleen-lezen). Huidige rechten zijn opnieuw gecontroleerd, maar deze versie kan niet worden gewijzigd of als actueel geëxporteerd.',
    queueAttentionCount: 'vaststelling(en) te bekijken van',
    queueDetectedSuffix:
      'gedetecteerde verwijzingen. Bekijk dekking afzonderlijk.',
    queueFilteredSuffix: 'verwijzing(en) in dit filter.',
    queueShortcutHint:
      'Op een geselecteerde verwijzing: J/K voor volgende/vorige, Spatie om te inspecteren. Sneltoetsen slaan geen beslissing op.',
    queueNoFlag: 'Geen automatische afwijking gemeld',
    readingSplitNote:
      'Beoordeling in drie panelen: conclusies en oorspronkelijk stuk blijven gescheiden. Versleep de scheidingslijn of gebruik de pijltjestoetsen.',
    readingDraftNote:
      'Focus op conclusies. De bron-PDF is verborgen, niet geverifieerd of genegeerd.',
    readingSourceNote:
      'Focus op bron. De bewaarde oorspronkelijke pagina blijft leidend voor inspectie.',
    sourceWidthLabel: 'Breedte bronpaneel:',
    restoreSourceWidth: 'Herstel 400px',
    draftPaneSubtitle: 'Bewaard DOCX · geëxtraheerde context',
    originalPdfTag: 'oorspronkelijke PDF',
    draftContextTitle: 'Bewaarde context in de DOCX-conclusies',
    draftContextNotice:
      'Begrensde platte tekst zonder Word-paginering of wijziging van het oorspronkelijke document.',
    draftContextLoading: 'Geautoriseerde conclusiecontext wordt geladen…',
    draftContextUnavailable:
      'Conclusiecontext niet beschikbaar; veronderstel het anker niet.',
    draftAnchorUnsupported:
      'Anker in het Word-document niet ondersteund of dubbelzinnig. Gok niet op de eerste alinea.',
    quoteCardTitle: 'Citaat en afgeleide brontekst',
    noGuardedTermNotice:
      'Dit bevroren rapport bevat geen controle op voorbehoudstermen. Inspecteer het oorspronkelijke stuk en de context vóór uw beslissing.',
    quoteCompareHint:
      'Vergelijk deze tekst met de oorspronkelijke pagina rechts. Een tekstovereenkomst bewijst geen juridische draagwijdte.',
    quoteInDraftHeading: 'Citaat in conclusies',
    quoteUnavailable: 'Geen ondersteund citaat beschikbaar in dit rapport.',
    extractedSourceHeading: 'Geëxtraheerde brontekst',
    extractedSourceUnavailable:
      'Geëxtraheerde brontekst niet beschikbaar of niet ondersteund. Inspecteer de oorspronkelijke pagina.',
    translationNotice:
      'Vertaling vereist menselijke beoordeling; conclusies en stuk kunnen in verschillende talen zijn opgesteld.',
    notSupplied: 'Niet opgegeven',
    pdfPageLabel: 'PDF-pagina',
    ofWord: 'van',
    zoomWord: 'Zoom',
    refPageMappingLabel: 'Paginering:',
    sourceScopeBody:
      'Broninspectie wijzigt identiteit, paginering, getrouwheid noch menselijke beoordeling. Geëxtraheerde tekst en kaders zijn enkel navigatiehulpmiddelen.',
    legalCorpusPrefix: 'Gekozen corpus:',
    legalCorpusArticles: 'artikelen, pakket',
    legalCorpusDisclaimer:
      'Geen garantie inzake toepasselijkheid of actuele geldigheid.',
    legalNoCorpus:
      'Er is geen corpus gekozen voor dit dossier. Geen enkel artikel kan worden geverifieerd.',
    legalReasonLabelPrefix: 'Reden:',
    legalClaimSupportUnassessed:
      'Juridische draagwijdte: door advocaat te beoordelen.',
    legalNoArticleStored: 'Geen bewaard artikel voor deze verwijzing.',
    legalNoRulesEvaluated:
      'Er is geen door de advocaat bepaalde voorwaarde geëvalueerd voor deze controle.',
    legalChoiceConfirm: 'Ik bevestig deze vaststelling zoals weergegeven',
    legalChoiceDismiss: 'Ik wijs deze vaststelling af',
    legalChoiceNeedsInfo: 'Bijkomende informatie vereist',
    legalLedgerUnavailable:
      'Het ondertekende register is niet beschikbaar. Er kan niets worden vastgelegd.',
    legalLedgerStale:
      'Het register is gekoppeld aan een andere controle. Herlaad vóór uw beslissing.',
  },
};

const STATE_VALUES: Record<Locale, Record<string, string>> = {
  en: {},
  fr: {
    resolved: 'Résolue',
    not_in_inventory: 'Absent du bordereau',
    source_missing: 'Pièce manquante',
    ambiguous: 'Renvoi ambigu',
    not_assessed: 'Non évalué',
    mapped: 'Page localisée',
    unmapped: 'Page non localisée',
    conflicting: 'Pagination en conflit',
    exact_match: 'Correspondance constatée',
    quote_not_found: 'Écart constaté',
    representation_conflict: 'Écart de source',
    ocr_unreliable: 'OCR illisible',
    translation_review_required: 'Traduction à apprécier',
    multiple_matches: 'Plusieurs passages',
    supported: 'Confirmé',
    qualified: 'Confirmé avec réserve',
    contradicted: 'Contredit',
  },
  nl: {
    resolved: 'Opgelost',
    not_in_inventory: 'Niet op inventaris',
    source_missing: 'Stuk ontbreekt',
    ambiguous: 'Dubbelzinnig',
    not_assessed: 'Niet beoordeeld',
    mapped: 'Pagina gekoppeld',
    unmapped: 'Niet gekoppeld',
    conflicting: 'Paginaconflict',
    exact_match: 'Overeenstemming vastgesteld',
    quote_not_found: 'Afwijking vastgesteld',
    representation_conflict: 'Bronconflict',
    ocr_unreliable: 'OCR onbetrouwbaar',
    translation_review_required: 'Vertaling te beoordelen',
    multiple_matches: 'Meerdere passages',
    supported: 'Bevestigd',
    qualified: 'Met voorbehoud',
    contradicted: 'Tegengesproken',
  },
};

const DIMENSION_LABELS: Record<Locale, Record<string, string>> = {
  en: {},
  fr: {
    Identity: 'Identité pièce',
    'Page mapping': 'Pagination',
    Fidelity: 'Fidélité citation',
    'Human support': 'Décision humaine',
  },
  nl: {
    Identity: 'Identiteit stuk',
    'Page mapping': 'Paginering',
    Fidelity: 'Citaatgetrouwheid',
    'Human support': 'Menselijke beoordeling',
  },
};

export interface LocaleContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: string) => string;
  stateLabel: (value: string) => string;
  dimensionLabel: (label: string) => string;
  legalStatusLabel: (status: string) => string;
  categoryLabel: (category: ResultCategory) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({
  children,
  initial,
}: {
  children: ReactNode;
  initial?: Locale;
}) {
  const [locale, setLocale] = useState<Locale>(
    () => initial ?? detectInitialLocale(),
  );
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const value = useMemo<LocaleContextValue>(() => {
    const dict = MESSAGES[locale];
    return {
      locale,
      setLocale,
      t: (key: string) => dict[key] ?? MESSAGES.en[key] ?? key,
      stateLabel: (raw: string) =>
        STATE_VALUES[locale][raw.toLowerCase()] ?? raw.replaceAll('_', ' '),
      dimensionLabel: (label: string) =>
        DIMENSION_LABELS[locale][label] ?? label,
      legalStatusLabel: (status: string) => {
        if (status === 'PASS') return dict.legalPass ?? status;
        if (status === 'FAIL') return dict.legalFail ?? status;
        if (status === 'UNVERIFIED') return dict.legalUnverified ?? status;
        if (status === 'UNDETERMINED') return dict.legalUndetermined ?? status;
        return status;
      },
      categoryLabel: (category: ResultCategory) => {
        const map: Record<ResultCategory, string> = {
          correspondance: dict.catCorrespondance ?? 'Literal match',
          ecart: dict.catEcart ?? 'Mismatch',
          impossible: dict.catImpossible ?? 'Check impossible',
          appreciation: dict.catAppreciation ?? 'Appraisal required',
        };
        return map[category];
      },
    };
  }, [locale]);

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (ctx) return ctx;
  return {
    locale: 'en',
    setLocale: () => {},
    t: (key: string) => MESSAGES.en[key] ?? key,
    stateLabel: (raw: string) => raw.replaceAll('_', ' '),
    dimensionLabel: (label: string) => label,
    legalStatusLabel: (status: string) => {
      if (status === 'PASS') return MESSAGES.en.legalPass ?? status;
      if (status === 'FAIL') return MESSAGES.en.legalFail ?? status;
      if (status === 'UNVERIFIED') return MESSAGES.en.legalUnverified ?? status;
      if (status === 'UNDETERMINED')
        return MESSAGES.en.legalUndetermined ?? status;
      return status;
    },
    categoryLabel: (category: ResultCategory) => {
      const map: Record<ResultCategory, string> = {
        correspondance: MESSAGES.en.catCorrespondance ?? 'Literal match',
        ecart: MESSAGES.en.catEcart ?? 'Mismatch',
        impossible: MESSAGES.en.catImpossible ?? 'Check impossible',
        appreciation: MESSAGES.en.catAppreciation ?? 'Appraisal required',
      };
      return map[category];
    },
  };
}

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();
  return (
    <div className="locale-switch" role="group" aria-label={t('languageLabel')}>
      {SUPPORTED.map((code) => (
        <button
          key={code}
          type="button"
          className="locale-btn"
          aria-pressed={locale === code}
          onClick={() => setLocale(code)}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
