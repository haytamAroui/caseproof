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
    legalChoiceOmission: 'A relevant passage or piece was not shown',
    legalLedgerUnavailable:
      'The review ledger is unavailable. Nothing can be recorded.',
    legalLedgerStale:
      'The ledger is bound to a different check. Reload before deciding.',
    packDownloadBtn: 'Download offline review pack (ZIP)',
    packPreparing: 'Preparing the pack…',
    packError:
      'The pack could not be prepared or its bytes did not match this check (the review may have changed). Nothing was saved. Reload and try again.',
    exhibitsHeading: 'Exhibit references and the confirmed inventory',
    exhibitsLoading: 'Loading exhibit references…',
    exhibitsError:
      'Exhibit references are unavailable. No cached result is shown.',
    exhibitsNone: 'No numbered exhibit mention was detected.',
    exhibitNotInInventory: 'Not in the confirmed inventory',
    exhibitUndetermined: 'Cannot be decided',
    conditionsHeading: 'Conditions defined by the lawyer',
    conditionsLoading: 'Loading conditions…',
    conditionsUnavailable:
      'Conditions are unavailable. Nothing can be shown or saved.',
    conditionsSaveBtn: 'Save condition',
    conditionsRemoveBtn: 'Remove',
    conditionsIdLabel: 'Identifier (lowercase, digits, dashes)',
    conditionsLabelField: 'Label',
    conditionsQuestionField: 'Question for the lawyer (optional)',
    conditionsTriggerField:
      'Words in the brief that trigger it (comma separated)',
    conditionsEvidenceField: 'Words to find in the pieces (comma separated)',
    conditionsPiecesField: 'Only these pieces (optional, e.g. Pièce 1)',
    conditionNoPassage: 'No passage found in the pieces read',
    triageSummaryLabel: 'Filter findings by verification category',
    bannerInventoryUnconfirmed:
      'Inventory not yet confirmed for this draft: dependent exhibit identities remain NOT_ASSESSED until you confirm mappings.',
    bannerInventoryAction: 'Confirm inventory',
    bannerInventoryInlineBtn: 'Inspect mappings inline',
    bannerInventoryInlineTitle:
      'Unconfirmed exhibit mappings (progressive preview)',
    bannerInventoryInlineHint:
      'These references remain NOT_ASSESSED until you confirm each Pièce/Stuk ↔ file link on the inventory screen.',
    linkConditionsLegal: 'Conditions & legal articles',
    omissionQuickBtn: 'Report missed passage',
    omissionQuickTitle: 'Log an omission note (quick shortcut)',
    omissionQuickHint:
      'If a relevant clause or exhibit passage was omitted from the draft or scan, record it as an explicit omission disposition in the Legal & Review workspace.',
    omissionQuickLink: 'Open legal & omission review',
    lexicalCueReservationTitle: 'Omitted reservation cue · Appraisal required',
    lexicalCueStatusDisclaimer:
      'Flagged for lawyer appraisal — not semantically verified.',
    ariaReferencesQueue: 'References',
    ariaReadingLayout: 'Reading layout',
    ariaQuotationDerived: 'Quotation and derived source text',
    ariaVerificationCoverage: 'Verification and processing coverage',
    ariaWordHandoff: 'Full Microsoft Word editing and signed import',
    ariaWordRoundtripParity: 'Word round-trip decision parity',
    bannerPaginationUnmapped:
      'Page-space conflict or unmapped pinpoint: PDF, printed, and bundle pages are tracked separately and never auto-equated.',
    bannerOcrUnreliable:
      'Unreadable or low-confidence scan detected: inspect the preserved original page pixels directly.',
    bannerPartialCoverage:
      'Partial DOCX coverage: some story regions (headers, footers, textboxes, or unsupported parts) were not scanned.',
    bannerFilterAction: 'Show affected',
    exhibitsConfirmedComplete: 'Inventory confirmed and declared complete',
    exhibitsConfirmedIncomplete: 'Inventory confirmed, not declared complete',
    exhibitsUnconfirmed:
      'No confirmed inventory for this draft. Nothing is mapped to a file.',
    exhibitsDetectedLabel: 'Detected:',
    exhibitsLocatedLabel: 'located in the inventory:',
    exhibitsContentNotCompared: 'Content not compared to the brief.',
    exhibitsUncitedPrefix:
      'Inventory entries with no mention detected in the assessed text:',
    exhibitsUncitedDisclaimer: 'This is not a finding that they are uncited.',
    statusCueFlagTitle: 'Lexical appraisal flag',
    statusCueFlagClaimVsSource: 'Draft wording vs. source wording:',
    statusCueFlagDisclaimer:
      'Targeted lexical cue only — does not verify legal meaning. Inspect the source passage and decide.',
    runImmediateUnconfirmedBtn: 'Run immediate audit (unconfirmed inventory)',
    reservationCueAdvisory:
      'Advisory, read with the article (status unchanged).',
    reservationCueOutside: 'Reservation word outside the quoted passage',
    reservationCueNegation: 'Negation word in the neighbouring sentence',
    reservationCueAround: 'Stored article text around it:',
    reportEyebrowHistorical: 'Historical report · read-only',
    reportEyebrowCurrent: 'Current preserved report',
    clearReferenceSearch: 'Clear reference search',
    noRefsDetected:
      'No explicit references were detected. Inspect processing coverage before drawing conclusions.',
    noRefsInFilter:
      'No references in this filter. Choose Show all to inspect the full scope.',
    bannerFailedSourcePages:
      'Unprocessed or failed source PDF pages detected in coverage. Inspect source coverage before drawing conclusions.',
    reopenSourceBtn: 'Reopen source',
    viewerPrevPage: 'Previous source page',
    viewerNextPage: 'Next source page',
    viewerZoomOut: 'Zoom out',
    viewerZoomIn: 'Zoom in',
    viewerRotatePage: 'Rotate page',
    legalDetectedPrefix: 'Detected:',
    legalLookedAtPrefix: 'Looked at:',
    legalNotLookedAtPrefix: 'Not looked at:',
    legalNotDetectedDisclaimer:
      'A citation the check does not detect is not a verified citation.',
    legalSourcePrefix: 'Source:',
    legalRowCheckedPrefix: 'This row checked:',
    legalNoQuotationOnly: 'no quotation (the citation only)',
    legalQuoteNotLocated: ' (its exact position could not be located)',
    legalHighlightLegend:
      'Solid highlight = what this row checked. Dashed = another citation or quotation in the same passage, checked separately in its own row',
    legalHighlightDisclaimerSuffix: 'here does not cover the dashed parts.',
    sourceOpenTimeout: 'PDF opening exceeded its time budget.',
    sourceOpenFailed:
      'This source could not be opened. It may be unavailable, unsupported or outside the inspection budget.',
    historicalOriginalPrefix: 'Historical original version · read-only.',
    filingPdfParityTitle: 'Final filing PDF vs. verified DOCX parity',
    filingPdfParityLead:
      'Before uploading to court (e-Deposit / DPA-Deposit), check that the exported PDF text layer matches this verified DOCX snapshot to catch accidental filing of an older draft.',
    filingPdfParityFileLabel: 'Final filing PDF (.pdf, max 10 MiB)',
    filingPdfParityRunBtn: 'Verify final PDF against this DOCX snapshot',
    filingPdfParityChecking:
      'Checking final PDF text layer against verified DOCX…',
    filingPdfParityError:
      'Filing PDF parity check could not run. Ensure a valid, unencrypted PDF (max 10 MiB, max 64 pages) matching the current draft.',
    filingPdfParityVerifiedDocxLabel: 'Verified DOCX SHA-256:',
    filingPdfParityPdfLabel: 'Checked filing PDF SHA-256:',
    filingPdfParityCountsPrefix: 'Pages:',
    filingPdfParityTokensPrefix: 'Tokens (DOCX / PDF):',
    filingPdfParityMissingTextPages:
      'Pages without extractable text layer (OCR unreliable — fail-closed):',
    filingPdfParityDiffsHeading: 'Detected text-layer differences',
    filingPdfParityDocxExcerpt: 'Verified DOCX:',
    filingPdfParityPdfExcerpt: 'Supplied PDF:',
    filingPdfParityReasonsLabel: 'Reason codes:',
    moreActionsLabel: 'More dossier actions',
    signInEmailLabel: 'Email address',
    signInPasswordLabel: 'Password',
    signInShowPassword: 'Show password',
    signInHidePassword: 'Hide password',
    signInSubmit: 'Sign in',
    signInSubmitting: 'Signing in…',
    signInHint:
      'Sign in with an existing workspace account. Reloading requires a fresh sign-in. Session material is kept in memory only.',
    exportsBackLink: 'Back to permitted reports',
    exportsEyebrow: 'F6 · M4 reviewed delivery',
    exportsTitle: 'Reviewed exports and history',
    exportsLead:
      'Releases preserve scope and uncertainty. They do not certify legal support, accuracy or court filing.',
    exportsPreviewHeading: 'Preview release scope',
    exportsHistoryHeading: 'Frozen release history',
    exportsHistoryEmpty: 'No reviewed releases exist for this brief.',
    exportsReviewDetailsBtn: 'Review release details',
    exportsNoEligibleError:
      'No reviewed release is eligible. Save a human decision for a detected finding before exporting.',
    exportsRecallNotMeasured: 'Reference detection recall was not measured.',
    exportsPendingInspectLabel: 'Inspect and review pending findings:',
    exportsReviewIncomplete:
      'Review incomplete. A complete-reviewed release is blocked.',
    exportsReviewComplete:
      'Review complete for detected findings only; this is not complete dossier coverage.',
    draftRegionPrefix: 'Story region',
    draftShaPrefix: 'original SHA-256',
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
    legalRulesHeading: 'Règles d’adéquation sur faits déclarés',
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
    legalUnverified: 'Absent du corpus choisi',
    legalUndetermined: 'Indéterminé (à examiner)',
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
    legalChoiceOmission:
      'Un passage ou une pièce pertinente n’a pas été affiché',
    legalLedgerUnavailable:
      'Le registre signé est indisponible. Aucune décision ne peut être enregistrée.',
    legalLedgerStale:
      'Le registre est lié à un autre contrôle. Rechargez avant de décider.',
    packDownloadBtn: 'Télécharger le pack de revue hors ligne (.zip)',
    packPreparing: 'Préparation du pack en cours…',
    packError:
      'Le pack n’a pas pu être préparé ou son empreinte ne correspond plus à ce contrôle. Rien n’a été enregistré. Rechargez la page.',
    exhibitsHeading: 'Renvois aux pièces et bordereau confirmé',
    exhibitsLoading: 'Chargement des renvois de pièces…',
    exhibitsError:
      'Les renvois de pièces sont indisponibles. Aucun résultat en cache n’est affiché.',
    exhibitsNone: 'Aucun renvoi numéroté à une pièce n’a été détecté.',
    exhibitNotInInventory: 'Absent du bordereau confirmé',
    exhibitUndetermined: 'Appréciation requise',
    conditionsHeading: 'Conditions définies par l’avocat',
    conditionsLoading: 'Chargement des conditions…',
    conditionsUnavailable:
      'Les conditions sont indisponibles. Rien ne peut être affiché ou enregistré.',
    conditionsSaveBtn: 'Enregistrer la condition',
    conditionsRemoveBtn: 'Supprimer',
    conditionsIdLabel: 'Identifiant (minuscules, chiffres, tirets)',
    conditionsLabelField: 'Intitulé de la condition',
    conditionsQuestionField: 'Question à l’avocat (optionnel)',
    conditionsTriggerField:
      'Mots déclencheurs dans les conclusions (séparés par des virgules)',
    conditionsEvidenceField:
      'Mots à retrouver dans les pièces (séparés par des virgules)',
    conditionsPiecesField: 'Limiter à ces pièces (optionnel, ex. Pièce 1)',
    conditionNoPassage: 'Aucun passage trouvé dans les pièces lues',
    triageSummaryLabel: 'Filtrer les constats par catégorie de contrôle',
    bannerInventoryUnconfirmed:
      'Bordereau non encore confirmé : les identités de pièces dépendantes restent « Non évalué » tant que vous ne confirmez pas le rapprochement.',
    bannerInventoryAction: 'Confirmer le bordereau',
    bannerInventoryInlineBtn: 'Voir les liaisons ici',
    bannerInventoryInlineTitle:
      'Liaisons de pièces non confirmées (aperçu progressif)',
    bannerInventoryInlineHint:
      'Ces renvois restent « Non évalué » tant que chaque lien Pièce/Stuk ↔ fichier n’est pas confirmé dans le bordereau.',
    linkConditionsLegal: 'Conditions & articles de loi',
    omissionQuickBtn: 'Signaler une omission',
    omissionQuickTitle: 'Signaler un passage omis (raccourci)',
    omissionQuickHint:
      'Si une clause ou une pièce pertinente manque dans les conclusions ou l’extrait, enregistrez une mention d’omission explicite dans l’espace Juridique & Revue.',
    omissionQuickLink: 'Ouvrir la revue juridique & omissions',
    lexicalCueReservationTitle:
      'Réserve d’ouverture omise · Appréciation requise',
    lexicalCueStatusDisclaimer:
      'Signalé à l’appréciation de l’avocat — non vérifié sémantiquement.',
    ariaReferencesQueue: 'Références détectées',
    ariaReadingLayout: 'Disposition de lecture',
    ariaQuotationDerived: 'Citation et texte dérivé de la pièce',
    ariaVerificationCoverage: 'Couverture de vérification et de traitement',
    ariaWordHandoff: 'Édition Microsoft Word complète et réimportation signée',
    ariaWordRoundtripParity: 'Parité des décisions après aller-retour Word',
    bannerPaginationUnmapped:
      'Pagination non localisée ou en conflit : page PDF, page imprimée et page dossier restent strictement séparées.',
    bannerOcrUnreliable:
      'Scan illisible ou OCR peu fiable détecté : consultez directement les pixels de la page originale conservée.',
    bannerPartialCoverage:
      'Couverture DOCX partielle : certaines zones (en-têtes, pieds de page, zones de texte ou éléments non pris en charge) n’ont pas été analysées.',
    bannerFilterAction: 'Afficher les constats',
    exhibitsConfirmedComplete: 'Bordereau confirmé et déclaré complet',
    exhibitsConfirmedIncomplete: 'Bordereau confirmé, non déclaré complet',
    exhibitsUnconfirmed:
      'Aucun bordereau confirmé pour ces conclusions. Aucune pièce n’est reliée à un fichier.',
    exhibitsDetectedLabel: 'Détectés :',
    exhibitsLocatedLabel: 'localisés au bordereau :',
    exhibitsContentNotCompared: 'Contenu non comparé aux conclusions.',
    exhibitsUncitedPrefix:
      'Entrées du bordereau sans mention détectée dans le texte analysé :',
    exhibitsUncitedDisclaimer:
      'Ceci ne constitue pas un constat d’absence de citation.',
    statusCueFlagTitle: 'Drapeau lexical · Appréciation requise',
    statusCueFlagClaimVsSource: 'Terme des conclusions vs. pièce :',
    statusCueFlagDisclaimer:
      'Signal lexical ciblé uniquement — ne vérifie pas le sens juridique. Consultez le passage original pour décider.',
    runImmediateUnconfirmedBtn:
      'Lancer l’audit immédiat (bordereau non confirmé)',
    reservationCueAdvisory:
      'Avis informatif, à lire avec l’article complet (statut inchangé).',
    reservationCueOutside: 'Mot de réserve hors du passage cité',
    reservationCueNegation: 'Mot de négation dans la phrase voisine',
    reservationCueAround: 'Texte conservé de l’article autour :',
    reportEyebrowHistorical: 'Rapport historique · lecture seule',
    reportEyebrowCurrent: 'Rapport conservé actuel',
    clearReferenceSearch: 'Effacer le filtre texte',
    noRefsDetected:
      'Aucun renvoi explicite n’a été détecté. Vérifiez la couverture d’analyse avant de conclure.',
    noRefsInFilter:
      'Aucun constat dans ce filtre. Choisissez « Tout afficher » pour consulter tout le périmètre.',
    bannerFailedSourcePages:
      'Pages PDF sources non traitées ou en échec dans la couverture. Vérifiez la couverture des sources avant de conclure.',
    reopenSourceBtn: 'Rouvrir la pièce source',
    viewerPrevPage: 'Page source précédente',
    viewerNextPage: 'Page source suivante',
    viewerZoomOut: 'Zoom arrière',
    viewerZoomIn: 'Zoom avant',
    viewerRotatePage: 'Pivoter la page',
    legalDetectedPrefix: 'Détectés :',
    legalLookedAtPrefix: 'Analysés :',
    legalNotLookedAtPrefix: 'Non analysés :',
    legalNotDetectedDisclaimer:
      'Une citation non détectée par le contrôle n’est pas une citation vérifiée.',
    legalSourcePrefix: 'Source :',
    legalRowCheckedPrefix: 'Passage contrôlé :',
    legalNoQuotationOnly: 'aucune citation textuelle (renvoi uniquement)',
    legalQuoteNotLocated: ' (position exacte non localisée)',
    legalHighlightLegend:
      'Surlignage plein = passage contrôlé par cette ligne. Pointillé = autre renvoi ou citation dans le même paragraphe, contrôlé séparément sur sa propre ligne',
    legalHighlightDisclaimerSuffix:
      'ici ne couvre pas les passages en pointillé.',
    sourceOpenTimeout: 'L’ouverture du PDF a dépassé le délai autorisé.',
    sourceOpenFailed:
      'Impossible d’ouvrir cette pièce source. Elle est peut-être indisponible, non prise en charge ou hors budget d’inspection.',
    historicalOriginalPrefix: 'Version originale historique · lecture seule.',
    filingPdfParityTitle: 'Parité PDF final de dépôt ↔ DOCX vérifié',
    filingPdfParityLead:
      'Avant le dépôt au greffe (e-Deposit / DPA-Deposit), vérifiez que la couche texte du PDF exporté correspond exactement à ce DOCX vérifié afin d’éviter le dépôt accidentel d’un ancien projet.',
    filingPdfParityFileLabel: 'PDF final à déposer (.pdf, max 10 Mio)',
    filingPdfParityRunBtn: 'Vérifier le PDF final par rapport à ce DOCX',
    filingPdfParityChecking:
      'Contrôle de la couche texte du PDF final par rapport au DOCX vérifié…',
    filingPdfParityError:
      'Impossible d’exécuter le contrôle de parité PDF. Vérifiez que le fichier est un PDF non chiffré valide (max 10 Mio, max 64 pages) pour la version courante.',
    filingPdfParityVerifiedDocxLabel: 'SHA-256 du DOCX vérifié :',
    filingPdfParityPdfLabel: 'SHA-256 du PDF contrôlé :',
    filingPdfParityCountsPrefix: 'Pages :',
    filingPdfParityTokensPrefix: 'Jetons (DOCX / PDF) :',
    filingPdfParityMissingTextPages:
      'Pages sans couche texte extractible (OCR non fiable — refus de validation) :',
    filingPdfParityDiffsHeading: 'Différences détectées dans la couche texte',
    filingPdfParityDocxExcerpt: 'DOCX vérifié :',
    filingPdfParityPdfExcerpt: 'PDF fourni :',
    filingPdfParityReasonsLabel: 'Codes de motif :',
    moreActionsLabel: 'Autres actions du dossier',
    signInEmailLabel: 'Adresse e-mail',
    signInPasswordLabel: 'Mot de passe',
    signInShowPassword: 'Afficher le mot de passe',
    signInHidePassword: 'Masquer le mot de passe',
    signInSubmit: 'Se connecter',
    signInSubmitting: 'Connexion…',
    signInHint:
      'Connectez-vous avec un compte autorisé. Un rechargement impose une nouvelle connexion ; la session reste uniquement en mémoire.',
    exportsBackLink: 'Retour aux rapports autorisés',
    exportsEyebrow: 'Clôture et export revu',
    exportsTitle: 'Exports revus et historique',
    exportsLead:
      'Les exports conservent le périmètre et l’incertitude. Ils ne certifient ni le fond juridique, ni l’exactitude, ni le dépôt au greffe.',
    exportsPreviewHeading: 'Aperçu du périmètre d’export',
    exportsHistoryHeading: 'Historique des exports figés',
    exportsHistoryEmpty:
      'Aucun export revu n’existe encore pour ces conclusions.',
    exportsReviewDetailsBtn: 'Examiner les détails de l’export',
    exportsNoEligibleError:
      'Aucun export revu n’est éligible. Enregistrez une décision humaine sur un constat détecté avant d’exporter.',
    exportsRecallNotMeasured:
      'Le taux de rappel de détection des renvois n’a pas été mesuré.',
    exportsPendingInspectLabel:
      'Examiner et décider sur les constats en attente :',
    exportsReviewIncomplete:
      'Revue incomplète. Un export « revue complète » reste bloqué.',
    exportsReviewComplete:
      'Revue achevée pour les constats détectés uniquement ; ceci ne constitue pas une couverture exhaustive du dossier.',
    draftRegionPrefix: 'Zone du document',
    draftShaPrefix: 'SHA-256 original',
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
    legalRulesHeading: 'Door de advocaat bepaalde regels op opgegeven feiten',
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
    legalUnverified: 'Niet in het gekozen corpus',
    legalUndetermined: 'Niet te bepalen (te beoordelen)',
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
    legalChoiceOmission: 'Een relevante passage of stuk werd niet getoond',
    legalLedgerUnavailable:
      'Het ondertekende register is niet beschikbaar. Er kan niets worden vastgelegd.',
    legalLedgerStale:
      'Het register is gekoppeld aan een andere controle. Herlaad vóór uw beslissing.',
    packDownloadBtn: 'Offline controlepakket downloaden (.zip)',
    packPreparing: 'Pakket wordt voorbereid…',
    packError:
      'Het pakket kon niet worden voorbereid of komt niet overeen met deze controle. Herlaad de pagina.',
    exhibitsHeading: 'Stukverwijzingen en bevestigde inventaris',
    exhibitsLoading: 'Stukverwijzingen laden…',
    exhibitsError:
      'Stukverwijzingen zijn niet beschikbaar. Er wordt geen cache getoond.',
    exhibitsNone: 'Geen genummerde stukverwijzing gedetecteerd.',
    exhibitNotInInventory: 'Niet op bevestigde inventaris',
    exhibitUndetermined: 'Beoordeling vereist',
    conditionsHeading: 'Door de advocaat bepaalde voorwaarden',
    conditionsLoading: 'Voorwaarden laden…',
    conditionsUnavailable:
      'Voorwaarden zijn niet beschikbaar. Er kan niets worden getoond of opgeslagen.',
    conditionsSaveBtn: 'Voorwaarde opslaan',
    conditionsRemoveBtn: 'Verwijderen',
    conditionsIdLabel: 'Identificatie (kleine letters, cijfers, streepjes)',
    conditionsLabelField: 'Titel van de voorwaarde',
    conditionsQuestionField: 'Vraag voor de advocaat (optioneel)',
    conditionsTriggerField:
      'Triggerwoorden in de conclusies (komma-gescheiden)',
    conditionsEvidenceField:
      'Te zoeken woorden in de stukken (komma-gescheiden)',
    conditionsPiecesField: 'Enkel deze stukken (optioneel, bv. Stuk 1)',
    conditionNoPassage: 'Geen passage gevonden in de gelezen stukken',
    triageSummaryLabel: 'Filter vaststellingen per controlecategorie',
    bannerInventoryUnconfirmed:
      'Inventaris nog niet bevestigd: afhankelijke stukidentiteiten blijven “Niet beoordeeld” tot u de koppeling bevestigt.',
    bannerInventoryAction: 'Inventaris bevestigen',
    bannerInventoryInlineBtn: 'Koppelingen hier bekijken',
    bannerInventoryInlineTitle:
      'Niet-bevestigde stukkoppelingen (progressief overzicht)',
    bannerInventoryInlineHint:
      'Deze verwijzingen blijven “Niet beoordeeld” tot elke Stuk/Pièce ↔ bestandskoppeling op het inventarisscherm is bevestigd.',
    linkConditionsLegal: 'Voorwaarden & wetsartikelen',
    omissionQuickBtn: 'Omissie melden',
    omissionQuickTitle: 'Ontbrekende passage melden (snelkoppeling)',
    omissionQuickHint:
      'Indien een relevante clausule of stukpassage ontbreekt in de conclusies of scan, registreer dit als expliciete omissiemelding in het juridisch overzicht.',
    omissionQuickLink: 'Open juridisch & omissie-overzicht',
    lexicalCueReservationTitle: 'Weggelaten voorbehoud · Beoordeling vereist',
    lexicalCueStatusDisclaimer:
      'Gemarkeerd voor beoordeling door de advocaat — niet semantisch geverifieerd.',
    ariaReferencesQueue: 'Gedetecteerde verwijzingen',
    ariaReadingLayout: 'Leesindeling',
    ariaQuotationDerived: 'Citaat en afgeleide brontekst',
    ariaVerificationCoverage: 'Controle- en verwerkingsdekking',
    ariaWordHandoff:
      'Volledige Microsoft Word-bewerking en ondertekende import',
    ariaWordRoundtripParity: 'Beslissingspariteit na Word-rondgang',
    bannerPaginationUnmapped:
      'Niet-gekoppelde of strijdige paginering: PDF-, gedrukte en bundelpagina’s blijven strikt gescheiden.',
    bannerOcrUnreliable:
      'Onleesbare of onbetrouwbare scan gedetecteerd: inspecteer rechtstreeks de bewaarde originele pagina.',
    bannerPartialCoverage:
      'Gedeeltelijke DOCX-dekking: bepaalde zones (kop-/voetteksten, tekstvakken of niet-ondersteunde delen) werden niet gescand.',
    bannerFilterAction: 'Betrokken tonen',
    exhibitsConfirmedComplete: 'Inventaris bevestigd en volledig verklaard',
    exhibitsConfirmedIncomplete:
      'Inventaris bevestigd, niet volledig verklaard',
    exhibitsUnconfirmed:
      'Geen bevestigde inventaris voor deze conclusies. Niets is aan een bestand gekoppeld.',
    exhibitsDetectedLabel: 'Gedetecteerd:',
    exhibitsLocatedLabel: 'teruggevonden op de inventaris:',
    exhibitsContentNotCompared: 'Inhoud niet vergeleken met de conclusies.',
    exhibitsUncitedPrefix:
      'Inventarisposten zonder gedetecteerde vermelding in de geanalyseerde tekst:',
    exhibitsUncitedDisclaimer:
      'Dit is geen vaststelling dat ze niet geciteerd werden.',
    statusCueFlagTitle: 'Lexicale vlag · Beoordeling vereist',
    statusCueFlagClaimVsSource: 'Formulering conclusies vs. stuk:',
    statusCueFlagDisclaimer:
      'Gerichte lexicale signalering — controleert geen juridische betekenis. Inspecteer de oorspronkelijke passage en beslis.',
    runImmediateUnconfirmedBtn:
      'Directe controle starten (inventaris niet bevestigd)',
    reservationCueAdvisory:
      'Adviesmelding, te lezen samen met het volledige artikel (status ongewijzigd).',
    reservationCueOutside: 'Voorbehoudswoord buiten de geciteerde passage',
    reservationCueNegation: 'Ontkenningswoord in de aangrenzende zin',
    reservationCueAround: 'Bewaarde artikeltekst rondom:',
    reportEyebrowHistorical: 'Historisch rapport · alleen-lezen',
    reportEyebrowCurrent: 'Actueel bewaard rapport',
    clearReferenceSearch: 'Zoekfilter wissen',
    noRefsDetected:
      'Geen expliciete verwijzingen gedetecteerd. Controleer de verwerkingsdekking vóór u conclusies trekt.',
    noRefsInFilter:
      'Geen vaststellingen in dit filter. Kies “Alles tonen” om het volledige bereik te bekijken.',
    bannerFailedSourcePages:
      'Niet-verwerkte of mislukte PDF-bronpagina’s gedetecteerd. Inspecteer de brondekking vóór u conclusies trekt.',
    reopenSourceBtn: 'Bron opnieuw openen',
    viewerPrevPage: 'Vorige bronpagina',
    viewerNextPage: 'Volgende bronpagina',
    viewerZoomOut: 'Uitzoomen',
    viewerZoomIn: 'Inzoomen',
    viewerRotatePage: 'Pagina draaien',
    legalDetectedPrefix: 'Gedetecteerd:',
    legalLookedAtPrefix: 'Geanalyseerd:',
    legalNotLookedAtPrefix: 'Niet geanalyseerd:',
    legalNotDetectedDisclaimer:
      'Een niet-gedetecteerde verwijzing is geen geverifieerde verwijzing.',
    legalSourcePrefix: 'Bron:',
    legalRowCheckedPrefix: 'Gecontroleerde passage:',
    legalNoQuotationOnly: 'geen citaat (enkel de verwijzing)',
    legalQuoteNotLocated: ' (exacte positie niet gevonden)',
    legalHighlightLegend:
      'Volle markering = gecontroleerd door deze rij. Gestippeld = andere verwijzing of citaat in dezelfde passage, afzonderlijk gecontroleerd op een eigen rij',
    legalHighlightDisclaimerSuffix: 'hier dekt de gestippelde delen niet.',
    sourceOpenTimeout: 'Het openen van de PDF overschreed het tijdsbudget.',
    sourceOpenFailed:
      'Deze bron kon niet worden geopend. Zij is mogelijk niet beschikbaar, niet ondersteund of buiten het inspectiebudget.',
    historicalOriginalPrefix: 'Historische originele versie · alleen-lezen.',
    filingPdfParityTitle:
      'Pariteit definitieve neerleggings-PDF ↔ geverifieerd DOCX',
    filingPdfParityLead:
      'Controleer vóór neerlegging (e-Deposit / DPA-Deposit) of de tekstlaag van de geëxporteerde PDF overeenstemt met deze geverifieerde DOCX-versie om vergissing met een ouder ontwerp te vermijden.',
    filingPdfParityFileLabel: 'Definitieve neerleggings-PDF (.pdf, max 10 MiB)',
    filingPdfParityRunBtn: 'Definitieve PDF controleren tegenover dit DOCX',
    filingPdfParityChecking:
      'Tekstlaag van definitieve PDF vergelijken met geverifieerd DOCX…',
    filingPdfParityError:
      'Pariteitscontrole van PDF mislukt. Gebruik een geldige, niet-versleutelde PDF (max 10 MiB, max 64 pagina’s) voor het huidige ontwerp.',
    filingPdfParityVerifiedDocxLabel: 'SHA-256 geverifieerd DOCX:',
    filingPdfParityPdfLabel: 'SHA-256 gecontroleerde PDF:',
    filingPdfParityCountsPrefix: 'Pagina’s:',
    filingPdfParityTokensPrefix: 'Tokens (DOCX / PDF):',
    filingPdfParityMissingTextPages:
      'Pagina’s zonder extraheerbare tekstlaag (OCR onbetrouwbaar — geblokkeerd):',
    filingPdfParityDiffsHeading: 'Vastgestelde verschillen in tekstlaag',
    filingPdfParityDocxExcerpt: 'Geverifieerd DOCX:',
    filingPdfParityPdfExcerpt: 'Aangeboden PDF:',
    filingPdfParityReasonsLabel: 'Redencodes:',
    moreActionsLabel: 'Meer dossieracties',
    signInEmailLabel: 'E-mailadres',
    signInPasswordLabel: 'Wachtwoord',
    signInShowPassword: 'Wachtwoord tonen',
    signInHidePassword: 'Wachtwoord verbergen',
    signInSubmit: 'Aanmelden',
    signInSubmitting: 'Aanmelden…',
    signInHint:
      'Meld u aan met een bestaand werkruimteaccount. Herladen vereist opnieuw aanmelden; de sessie blijft uitsluitend in het geheugen.',
    exportsBackLink: 'Terug naar toegestane rapporten',
    exportsEyebrow: 'Afsluiting en beoordeelde export',
    exportsTitle: 'Beoordeelde exports en historiek',
    exportsLead:
      'Exports bewaren het bereik en de onzekerheid. Zij certificeren geen juridische steun, juistheid of neerlegging ter griffie.',
    exportsPreviewHeading: 'Voorbeeld van exportbereik',
    exportsHistoryHeading: 'Historiek van bevroren exports',
    exportsHistoryEmpty:
      'Er bestaan nog geen beoordeelde exports voor deze conclusies.',
    exportsReviewDetailsBtn: 'Exportdetails bekijken',
    exportsNoEligibleError:
      'Geen beoordeelde export mogelijk. Sla eerst een menselijke beslissing op voor een vaststelling.',
    exportsRecallNotMeasured:
      'De detectiegraad van verwijzingen werd niet gemeten.',
    exportsPendingInspectLabel:
      'Inspecteer en beoordeel openstaande vaststellingen:',
    exportsReviewIncomplete:
      'Beoordeling onvolledig. Een volledige export blijft geblokkeerd.',
    exportsReviewComplete:
      'Beoordeling voltooid voor gedetecteerde vaststellingen; dit betekent geen volledige dossierdekking.',
    draftRegionPrefix: 'Documentzone',
    draftShaPrefix: 'originele SHA-256',
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
    match_observed: 'Correspondance constatée',
    mismatch_detected: 'Écart constaté',
    cannot_verify: 'Contrôle impossible',
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
    match_observed: 'Overeenstemming vastgesteld',
    mismatch_detected: 'Afwijking vastgesteld',
    cannot_verify: 'Controle onmogelijk',
  },
};

const DIMENSION_LABELS: Record<Locale, Record<string, string>> = {
  en: {},
  fr: {
    Identity: 'Identité pièce',
    'Page mapping': 'Pagination',
    Fidelity: 'Fidélité citation',
    'Human support': 'Décision humaine',
    'Human support (frozen report)': 'Décision humaine (rapport figé)',
  },
  nl: {
    Identity: 'Identiteit stuk',
    'Page mapping': 'Paginering',
    Fidelity: 'Citaatgetrouwheid',
    'Human support': 'Menselijke beoordeling',
    'Human support (frozen report)':
      'Menselijke beoordeling (bevroren rapport)',
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
