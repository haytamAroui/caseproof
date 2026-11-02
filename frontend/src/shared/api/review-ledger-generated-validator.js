import lengthModule from 'ajv/dist/runtime/ucs2length.js';
const unicodeLength =
  typeof lengthModule === 'function' ? lengthModule : lengthModule.default;
('use strict');
export const validate = validate20;
export default validate20;
const schema31 = {
  $defs: {
    ReviewDecisionView: {
      additionalProperties: false,
      description:
        'A persisted signed human disposition, never a machine finding.',
      properties: {
        decision: {
          enum: [
            'CONFIRMED_SUPPORTED',
            'CONFIRMED_QUALIFIED',
            'CONFIRMED_CONTRADICTED',
          ],
          title: 'Decision',
          type: 'string',
        },
        rationale: {
          maxLength: 2000,
          minLength: 1,
          title: 'Rationale',
          type: 'string',
        },
        reference_id: {
          maxLength: 200,
          minLength: 1,
          title: 'Reference Id',
          type: 'string',
        },
        request_id: {
          maxLength: 100,
          minLength: 1,
          title: 'Request Id',
          type: 'string',
        },
        reviewed_region_ids: {
          items: { type: 'string' },
          maxItems: 96,
          title: 'Reviewed Region Ids',
          type: 'array',
        },
        reviewer_id: {
          maxLength: 200,
          minLength: 1,
          title: 'Reviewer Id',
          type: 'string',
        },
        timestamp: {
          maxLength: 64,
          minLength: 1,
          title: 'Timestamp',
          type: 'string',
        },
      },
      required: [
        'reference_id',
        'decision',
        'rationale',
        'reviewer_id',
        'request_id',
        'timestamp',
        'reviewed_region_ids',
      ],
      title: 'ReviewDecisionView',
      type: 'object',
    },
  },
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  additionalProperties: false,
  properties: {
    brief_id: {
      maxLength: 200,
      minLength: 1,
      title: 'Brief Id',
      type: 'string',
    },
    case_id: { maxLength: 200, minLength: 1, title: 'Case Id', type: 'string' },
    decisions: {
      items: { $ref: '#/$defs/ReviewDecisionView' },
      maxItems: 10000,
      title: 'Decisions',
      type: 'array',
    },
    schema: {
      const: 'caseproof-review-ledger-v1',
      title: 'Schema',
      type: 'string',
    },
    snapshot_hash: {
      pattern: '^[0-9a-f]{64}$',
      title: 'Snapshot Hash',
      type: 'string',
    },
  },
  required: ['schema', 'case_id', 'brief_id', 'snapshot_hash', 'decisions'],
  title: 'ReviewLedgerView',
  type: 'object',
};
const schema32 = {
  additionalProperties: false,
  description: 'A persisted signed human disposition, never a machine finding.',
  properties: {
    decision: {
      enum: [
        'CONFIRMED_SUPPORTED',
        'CONFIRMED_QUALIFIED',
        'CONFIRMED_CONTRADICTED',
      ],
      title: 'Decision',
      type: 'string',
    },
    rationale: {
      maxLength: 2000,
      minLength: 1,
      title: 'Rationale',
      type: 'string',
    },
    reference_id: {
      maxLength: 200,
      minLength: 1,
      title: 'Reference Id',
      type: 'string',
    },
    request_id: {
      maxLength: 100,
      minLength: 1,
      title: 'Request Id',
      type: 'string',
    },
    reviewed_region_ids: {
      items: { type: 'string' },
      maxItems: 96,
      title: 'Reviewed Region Ids',
      type: 'array',
    },
    reviewer_id: {
      maxLength: 200,
      minLength: 1,
      title: 'Reviewer Id',
      type: 'string',
    },
    timestamp: {
      maxLength: 64,
      minLength: 1,
      title: 'Timestamp',
      type: 'string',
    },
  },
  required: [
    'reference_id',
    'decision',
    'rationale',
    'reviewer_id',
    'request_id',
    'timestamp',
    'reviewed_region_ids',
  ],
  title: 'ReviewDecisionView',
  type: 'object',
};
const func1 = unicodeLength;
const pattern4 = new RegExp('^[0-9a-f]{64}$', 'u');
function validate20(
  data,
  {
    instancePath = '',
    parentData,
    parentDataProperty,
    rootData = data,
    dynamicAnchors = {},
  } = {},
) {
  let vErrors = null;
  let errors = 0;
  const evaluated0 = validate20.evaluated;
  if (evaluated0.dynamicProps) {
    evaluated0.props = undefined;
  }
  if (evaluated0.dynamicItems) {
    evaluated0.items = undefined;
  }
  if (errors === 0) {
    if (data && typeof data == 'object' && !Array.isArray(data)) {
      let missing0;
      if (
        (data.schema === undefined && (missing0 = 'schema')) ||
        (data.case_id === undefined && (missing0 = 'case_id')) ||
        (data.brief_id === undefined && (missing0 = 'brief_id')) ||
        (data.snapshot_hash === undefined && (missing0 = 'snapshot_hash')) ||
        (data.decisions === undefined && (missing0 = 'decisions'))
      ) {
        validate20.errors = [
          {
            instancePath,
            schemaPath: '#/required',
            keyword: 'required',
            params: { missingProperty: missing0 },
            message: "must have required property '" + missing0 + "'",
          },
        ];
        return false;
      } else {
        const _errs1 = errors;
        for (const key0 in data) {
          if (!(
            key0 === 'brief_id' ||
            key0 === 'case_id' ||
            key0 === 'decisions' ||
            key0 === 'schema' ||
            key0 === 'snapshot_hash'
          )) {
            validate20.errors = [
              {
                instancePath,
                schemaPath: '#/additionalProperties',
                keyword: 'additionalProperties',
                params: { additionalProperty: key0 },
                message: 'must NOT have additional properties',
              },
            ];
            return false;
            break;
          }
        }
        if (_errs1 === errors) {
          if (data.brief_id !== undefined) {
            let data0 = data.brief_id;
            const _errs2 = errors;
            if (errors === _errs2) {
              if (typeof data0 === 'string') {
                if (func1(data0) > 200) {
                  validate20.errors = [
                    {
                      instancePath: instancePath + '/brief_id',
                      schemaPath: '#/properties/brief_id/maxLength',
                      keyword: 'maxLength',
                      params: { limit: 200 },
                      message: 'must NOT have more than 200 characters',
                    },
                  ];
                  return false;
                } else {
                  if (func1(data0) < 1) {
                    validate20.errors = [
                      {
                        instancePath: instancePath + '/brief_id',
                        schemaPath: '#/properties/brief_id/minLength',
                        keyword: 'minLength',
                        params: { limit: 1 },
                        message: 'must NOT have fewer than 1 characters',
                      },
                    ];
                    return false;
                  }
                }
              } else {
                validate20.errors = [
                  {
                    instancePath: instancePath + '/brief_id',
                    schemaPath: '#/properties/brief_id/type',
                    keyword: 'type',
                    params: { type: 'string' },
                    message: 'must be string',
                  },
                ];
                return false;
              }
            }
            var valid0 = _errs2 === errors;
          } else {
            var valid0 = true;
          }
          if (valid0) {
            if (data.case_id !== undefined) {
              let data1 = data.case_id;
              const _errs4 = errors;
              if (errors === _errs4) {
                if (typeof data1 === 'string') {
                  if (func1(data1) > 200) {
                    validate20.errors = [
                      {
                        instancePath: instancePath + '/case_id',
                        schemaPath: '#/properties/case_id/maxLength',
                        keyword: 'maxLength',
                        params: { limit: 200 },
                        message: 'must NOT have more than 200 characters',
                      },
                    ];
                    return false;
                  } else {
                    if (func1(data1) < 1) {
                      validate20.errors = [
                        {
                          instancePath: instancePath + '/case_id',
                          schemaPath: '#/properties/case_id/minLength',
                          keyword: 'minLength',
                          params: { limit: 1 },
                          message: 'must NOT have fewer than 1 characters',
                        },
                      ];
                      return false;
                    }
                  }
                } else {
                  validate20.errors = [
                    {
                      instancePath: instancePath + '/case_id',
                      schemaPath: '#/properties/case_id/type',
                      keyword: 'type',
                      params: { type: 'string' },
                      message: 'must be string',
                    },
                  ];
                  return false;
                }
              }
              var valid0 = _errs4 === errors;
            } else {
              var valid0 = true;
            }
            if (valid0) {
              if (data.decisions !== undefined) {
                let data2 = data.decisions;
                const _errs6 = errors;
                if (errors === _errs6) {
                  if (Array.isArray(data2)) {
                    if (data2.length > 10000) {
                      validate20.errors = [
                        {
                          instancePath: instancePath + '/decisions',
                          schemaPath: '#/properties/decisions/maxItems',
                          keyword: 'maxItems',
                          params: { limit: 10000 },
                          message: 'must NOT have more than 10000 items',
                        },
                      ];
                      return false;
                    } else {
                      var valid1 = true;
                      const len0 = data2.length;
                      for (let i0 = 0; i0 < len0; i0++) {
                        let data3 = data2[i0];
                        const _errs8 = errors;
                        const _errs9 = errors;
                        if (errors === _errs9) {
                          if (
                            data3 &&
                            typeof data3 == 'object' &&
                            !Array.isArray(data3)
                          ) {
                            let missing1;
                            if (
                              (data3.reference_id === undefined &&
                                (missing1 = 'reference_id')) ||
                              (data3.decision === undefined &&
                                (missing1 = 'decision')) ||
                              (data3.rationale === undefined &&
                                (missing1 = 'rationale')) ||
                              (data3.reviewer_id === undefined &&
                                (missing1 = 'reviewer_id')) ||
                              (data3.request_id === undefined &&
                                (missing1 = 'request_id')) ||
                              (data3.timestamp === undefined &&
                                (missing1 = 'timestamp')) ||
                              (data3.reviewed_region_ids === undefined &&
                                (missing1 = 'reviewed_region_ids'))
                            ) {
                              validate20.errors = [
                                {
                                  instancePath:
                                    instancePath + '/decisions/' + i0,
                                  schemaPath:
                                    '#/$defs/ReviewDecisionView/required',
                                  keyword: 'required',
                                  params: { missingProperty: missing1 },
                                  message:
                                    "must have required property '" +
                                    missing1 +
                                    "'",
                                },
                              ];
                              return false;
                            } else {
                              const _errs11 = errors;
                              for (const key1 in data3) {
                                if (!(
                                  key1 === 'decision' ||
                                  key1 === 'rationale' ||
                                  key1 === 'reference_id' ||
                                  key1 === 'request_id' ||
                                  key1 === 'reviewed_region_ids' ||
                                  key1 === 'reviewer_id' ||
                                  key1 === 'timestamp'
                                )) {
                                  validate20.errors = [
                                    {
                                      instancePath:
                                        instancePath + '/decisions/' + i0,
                                      schemaPath:
                                        '#/$defs/ReviewDecisionView/additionalProperties',
                                      keyword: 'additionalProperties',
                                      params: { additionalProperty: key1 },
                                      message:
                                        'must NOT have additional properties',
                                    },
                                  ];
                                  return false;
                                  break;
                                }
                              }
                              if (_errs11 === errors) {
                                if (data3.decision !== undefined) {
                                  let data4 = data3.decision;
                                  const _errs12 = errors;
                                  if (typeof data4 !== 'string') {
                                    validate20.errors = [
                                      {
                                        instancePath:
                                          instancePath +
                                          '/decisions/' +
                                          i0 +
                                          '/decision',
                                        schemaPath:
                                          '#/$defs/ReviewDecisionView/properties/decision/type',
                                        keyword: 'type',
                                        params: { type: 'string' },
                                        message: 'must be string',
                                      },
                                    ];
                                    return false;
                                  }
                                  if (!(
                                    data4 === 'CONFIRMED_SUPPORTED' ||
                                    data4 === 'CONFIRMED_QUALIFIED' ||
                                    data4 === 'CONFIRMED_CONTRADICTED'
                                  )) {
                                    validate20.errors = [
                                      {
                                        instancePath:
                                          instancePath +
                                          '/decisions/' +
                                          i0 +
                                          '/decision',
                                        schemaPath:
                                          '#/$defs/ReviewDecisionView/properties/decision/enum',
                                        keyword: 'enum',
                                        params: {
                                          allowedValues:
                                            schema32.properties.decision.enum,
                                        },
                                        message:
                                          'must be equal to one of the allowed values',
                                      },
                                    ];
                                    return false;
                                  }
                                  var valid3 = _errs12 === errors;
                                } else {
                                  var valid3 = true;
                                }
                                if (valid3) {
                                  if (data3.rationale !== undefined) {
                                    let data5 = data3.rationale;
                                    const _errs14 = errors;
                                    if (errors === _errs14) {
                                      if (typeof data5 === 'string') {
                                        if (func1(data5) > 2000) {
                                          validate20.errors = [
                                            {
                                              instancePath:
                                                instancePath +
                                                '/decisions/' +
                                                i0 +
                                                '/rationale',
                                              schemaPath:
                                                '#/$defs/ReviewDecisionView/properties/rationale/maxLength',
                                              keyword: 'maxLength',
                                              params: { limit: 2000 },
                                              message:
                                                'must NOT have more than 2000 characters',
                                            },
                                          ];
                                          return false;
                                        } else {
                                          if (func1(data5) < 1) {
                                            validate20.errors = [
                                              {
                                                instancePath:
                                                  instancePath +
                                                  '/decisions/' +
                                                  i0 +
                                                  '/rationale',
                                                schemaPath:
                                                  '#/$defs/ReviewDecisionView/properties/rationale/minLength',
                                                keyword: 'minLength',
                                                params: { limit: 1 },
                                                message:
                                                  'must NOT have fewer than 1 characters',
                                              },
                                            ];
                                            return false;
                                          }
                                        }
                                      } else {
                                        validate20.errors = [
                                          {
                                            instancePath:
                                              instancePath +
                                              '/decisions/' +
                                              i0 +
                                              '/rationale',
                                            schemaPath:
                                              '#/$defs/ReviewDecisionView/properties/rationale/type',
                                            keyword: 'type',
                                            params: { type: 'string' },
                                            message: 'must be string',
                                          },
                                        ];
                                        return false;
                                      }
                                    }
                                    var valid3 = _errs14 === errors;
                                  } else {
                                    var valid3 = true;
                                  }
                                  if (valid3) {
                                    if (data3.reference_id !== undefined) {
                                      let data6 = data3.reference_id;
                                      const _errs16 = errors;
                                      if (errors === _errs16) {
                                        if (typeof data6 === 'string') {
                                          if (func1(data6) > 200) {
                                            validate20.errors = [
                                              {
                                                instancePath:
                                                  instancePath +
                                                  '/decisions/' +
                                                  i0 +
                                                  '/reference_id',
                                                schemaPath:
                                                  '#/$defs/ReviewDecisionView/properties/reference_id/maxLength',
                                                keyword: 'maxLength',
                                                params: { limit: 200 },
                                                message:
                                                  'must NOT have more than 200 characters',
                                              },
                                            ];
                                            return false;
                                          } else {
                                            if (func1(data6) < 1) {
                                              validate20.errors = [
                                                {
                                                  instancePath:
                                                    instancePath +
                                                    '/decisions/' +
                                                    i0 +
                                                    '/reference_id',
                                                  schemaPath:
                                                    '#/$defs/ReviewDecisionView/properties/reference_id/minLength',
                                                  keyword: 'minLength',
                                                  params: { limit: 1 },
                                                  message:
                                                    'must NOT have fewer than 1 characters',
                                                },
                                              ];
                                              return false;
                                            }
                                          }
                                        } else {
                                          validate20.errors = [
                                            {
                                              instancePath:
                                                instancePath +
                                                '/decisions/' +
                                                i0 +
                                                '/reference_id',
                                              schemaPath:
                                                '#/$defs/ReviewDecisionView/properties/reference_id/type',
                                              keyword: 'type',
                                              params: { type: 'string' },
                                              message: 'must be string',
                                            },
                                          ];
                                          return false;
                                        }
                                      }
                                      var valid3 = _errs16 === errors;
                                    } else {
                                      var valid3 = true;
                                    }
                                    if (valid3) {
                                      if (data3.request_id !== undefined) {
                                        let data7 = data3.request_id;
                                        const _errs18 = errors;
                                        if (errors === _errs18) {
                                          if (typeof data7 === 'string') {
                                            if (func1(data7) > 100) {
                                              validate20.errors = [
                                                {
                                                  instancePath:
                                                    instancePath +
                                                    '/decisions/' +
                                                    i0 +
                                                    '/request_id',
                                                  schemaPath:
                                                    '#/$defs/ReviewDecisionView/properties/request_id/maxLength',
                                                  keyword: 'maxLength',
                                                  params: { limit: 100 },
                                                  message:
                                                    'must NOT have more than 100 characters',
                                                },
                                              ];
                                              return false;
                                            } else {
                                              if (func1(data7) < 1) {
                                                validate20.errors = [
                                                  {
                                                    instancePath:
                                                      instancePath +
                                                      '/decisions/' +
                                                      i0 +
                                                      '/request_id',
                                                    schemaPath:
                                                      '#/$defs/ReviewDecisionView/properties/request_id/minLength',
                                                    keyword: 'minLength',
                                                    params: { limit: 1 },
                                                    message:
                                                      'must NOT have fewer than 1 characters',
                                                  },
                                                ];
                                                return false;
                                              }
                                            }
                                          } else {
                                            validate20.errors = [
                                              {
                                                instancePath:
                                                  instancePath +
                                                  '/decisions/' +
                                                  i0 +
                                                  '/request_id',
                                                schemaPath:
                                                  '#/$defs/ReviewDecisionView/properties/request_id/type',
                                                keyword: 'type',
                                                params: { type: 'string' },
                                                message: 'must be string',
                                              },
                                            ];
                                            return false;
                                          }
                                        }
                                        var valid3 = _errs18 === errors;
                                      } else {
                                        var valid3 = true;
                                      }
                                      if (valid3) {
                                        if (
                                          data3.reviewed_region_ids !==
                                          undefined
                                        ) {
                                          let data8 = data3.reviewed_region_ids;
                                          const _errs20 = errors;
                                          if (errors === _errs20) {
                                            if (Array.isArray(data8)) {
                                              if (data8.length > 96) {
                                                validate20.errors = [
                                                  {
                                                    instancePath:
                                                      instancePath +
                                                      '/decisions/' +
                                                      i0 +
                                                      '/reviewed_region_ids',
                                                    schemaPath:
                                                      '#/$defs/ReviewDecisionView/properties/reviewed_region_ids/maxItems',
                                                    keyword: 'maxItems',
                                                    params: { limit: 96 },
                                                    message:
                                                      'must NOT have more than 96 items',
                                                  },
                                                ];
                                                return false;
                                              } else {
                                                var valid4 = true;
                                                const len1 = data8.length;
                                                for (
                                                  let i1 = 0;
                                                  i1 < len1;
                                                  i1++
                                                ) {
                                                  const _errs22 = errors;
                                                  if (
                                                    typeof data8[i1] !==
                                                    'string'
                                                  ) {
                                                    validate20.errors = [
                                                      {
                                                        instancePath:
                                                          instancePath +
                                                          '/decisions/' +
                                                          i0 +
                                                          '/reviewed_region_ids/' +
                                                          i1,
                                                        schemaPath:
                                                          '#/$defs/ReviewDecisionView/properties/reviewed_region_ids/items/type',
                                                        keyword: 'type',
                                                        params: {
                                                          type: 'string',
                                                        },
                                                        message:
                                                          'must be string',
                                                      },
                                                    ];
                                                    return false;
                                                  }
                                                  var valid4 =
                                                    _errs22 === errors;
                                                  if (!valid4) {
                                                    break;
                                                  }
                                                }
                                              }
                                            } else {
                                              validate20.errors = [
                                                {
                                                  instancePath:
                                                    instancePath +
                                                    '/decisions/' +
                                                    i0 +
                                                    '/reviewed_region_ids',
                                                  schemaPath:
                                                    '#/$defs/ReviewDecisionView/properties/reviewed_region_ids/type',
                                                  keyword: 'type',
                                                  params: { type: 'array' },
                                                  message: 'must be array',
                                                },
                                              ];
                                              return false;
                                            }
                                          }
                                          var valid3 = _errs20 === errors;
                                        } else {
                                          var valid3 = true;
                                        }
                                        if (valid3) {
                                          if (data3.reviewer_id !== undefined) {
                                            let data10 = data3.reviewer_id;
                                            const _errs24 = errors;
                                            if (errors === _errs24) {
                                              if (typeof data10 === 'string') {
                                                if (func1(data10) > 200) {
                                                  validate20.errors = [
                                                    {
                                                      instancePath:
                                                        instancePath +
                                                        '/decisions/' +
                                                        i0 +
                                                        '/reviewer_id',
                                                      schemaPath:
                                                        '#/$defs/ReviewDecisionView/properties/reviewer_id/maxLength',
                                                      keyword: 'maxLength',
                                                      params: { limit: 200 },
                                                      message:
                                                        'must NOT have more than 200 characters',
                                                    },
                                                  ];
                                                  return false;
                                                } else {
                                                  if (func1(data10) < 1) {
                                                    validate20.errors = [
                                                      {
                                                        instancePath:
                                                          instancePath +
                                                          '/decisions/' +
                                                          i0 +
                                                          '/reviewer_id',
                                                        schemaPath:
                                                          '#/$defs/ReviewDecisionView/properties/reviewer_id/minLength',
                                                        keyword: 'minLength',
                                                        params: { limit: 1 },
                                                        message:
                                                          'must NOT have fewer than 1 characters',
                                                      },
                                                    ];
                                                    return false;
                                                  }
                                                }
                                              } else {
                                                validate20.errors = [
                                                  {
                                                    instancePath:
                                                      instancePath +
                                                      '/decisions/' +
                                                      i0 +
                                                      '/reviewer_id',
                                                    schemaPath:
                                                      '#/$defs/ReviewDecisionView/properties/reviewer_id/type',
                                                    keyword: 'type',
                                                    params: { type: 'string' },
                                                    message: 'must be string',
                                                  },
                                                ];
                                                return false;
                                              }
                                            }
                                            var valid3 = _errs24 === errors;
                                          } else {
                                            var valid3 = true;
                                          }
                                          if (valid3) {
                                            if (data3.timestamp !== undefined) {
                                              let data11 = data3.timestamp;
                                              const _errs26 = errors;
                                              if (errors === _errs26) {
                                                if (
                                                  typeof data11 === 'string'
                                                ) {
                                                  if (func1(data11) > 64) {
                                                    validate20.errors = [
                                                      {
                                                        instancePath:
                                                          instancePath +
                                                          '/decisions/' +
                                                          i0 +
                                                          '/timestamp',
                                                        schemaPath:
                                                          '#/$defs/ReviewDecisionView/properties/timestamp/maxLength',
                                                        keyword: 'maxLength',
                                                        params: { limit: 64 },
                                                        message:
                                                          'must NOT have more than 64 characters',
                                                      },
                                                    ];
                                                    return false;
                                                  } else {
                                                    if (func1(data11) < 1) {
                                                      validate20.errors = [
                                                        {
                                                          instancePath:
                                                            instancePath +
                                                            '/decisions/' +
                                                            i0 +
                                                            '/timestamp',
                                                          schemaPath:
                                                            '#/$defs/ReviewDecisionView/properties/timestamp/minLength',
                                                          keyword: 'minLength',
                                                          params: { limit: 1 },
                                                          message:
                                                            'must NOT have fewer than 1 characters',
                                                        },
                                                      ];
                                                      return false;
                                                    }
                                                  }
                                                } else {
                                                  validate20.errors = [
                                                    {
                                                      instancePath:
                                                        instancePath +
                                                        '/decisions/' +
                                                        i0 +
                                                        '/timestamp',
                                                      schemaPath:
                                                        '#/$defs/ReviewDecisionView/properties/timestamp/type',
                                                      keyword: 'type',
                                                      params: {
                                                        type: 'string',
                                                      },
                                                      message: 'must be string',
                                                    },
                                                  ];
                                                  return false;
                                                }
                                              }
                                              var valid3 = _errs26 === errors;
                                            } else {
                                              var valid3 = true;
                                            }
                                          }
                                        }
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          } else {
                            validate20.errors = [
                              {
                                instancePath: instancePath + '/decisions/' + i0,
                                schemaPath: '#/$defs/ReviewDecisionView/type',
                                keyword: 'type',
                                params: { type: 'object' },
                                message: 'must be object',
                              },
                            ];
                            return false;
                          }
                        }
                        var valid1 = _errs8 === errors;
                        if (!valid1) {
                          break;
                        }
                      }
                    }
                  } else {
                    validate20.errors = [
                      {
                        instancePath: instancePath + '/decisions',
                        schemaPath: '#/properties/decisions/type',
                        keyword: 'type',
                        params: { type: 'array' },
                        message: 'must be array',
                      },
                    ];
                    return false;
                  }
                }
                var valid0 = _errs6 === errors;
              } else {
                var valid0 = true;
              }
              if (valid0) {
                if (data.schema !== undefined) {
                  let data12 = data.schema;
                  const _errs28 = errors;
                  if (typeof data12 !== 'string') {
                    validate20.errors = [
                      {
                        instancePath: instancePath + '/schema',
                        schemaPath: '#/properties/schema/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ];
                    return false;
                  }
                  if ('caseproof-review-ledger-v1' !== data12) {
                    validate20.errors = [
                      {
                        instancePath: instancePath + '/schema',
                        schemaPath: '#/properties/schema/const',
                        keyword: 'const',
                        params: { allowedValue: 'caseproof-review-ledger-v1' },
                        message: 'must be equal to constant',
                      },
                    ];
                    return false;
                  }
                  var valid0 = _errs28 === errors;
                } else {
                  var valid0 = true;
                }
                if (valid0) {
                  if (data.snapshot_hash !== undefined) {
                    let data13 = data.snapshot_hash;
                    const _errs30 = errors;
                    if (errors === _errs30) {
                      if (typeof data13 === 'string') {
                        if (!pattern4.test(data13)) {
                          validate20.errors = [
                            {
                              instancePath: instancePath + '/snapshot_hash',
                              schemaPath: '#/properties/snapshot_hash/pattern',
                              keyword: 'pattern',
                              params: { pattern: '^[0-9a-f]{64}$' },
                              message:
                                'must match pattern "' + '^[0-9a-f]{64}$' + '"',
                            },
                          ];
                          return false;
                        }
                      } else {
                        validate20.errors = [
                          {
                            instancePath: instancePath + '/snapshot_hash',
                            schemaPath: '#/properties/snapshot_hash/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ];
                        return false;
                      }
                    }
                    var valid0 = _errs30 === errors;
                  } else {
                    var valid0 = true;
                  }
                }
              }
            }
          }
        }
      }
    } else {
      validate20.errors = [
        {
          instancePath,
          schemaPath: '#/type',
          keyword: 'type',
          params: { type: 'object' },
          message: 'must be object',
        },
      ];
      return false;
    }
  }
  validate20.errors = vErrors;
  return errors === 0;
}
validate20.evaluated = {
  props: true,
  dynamicProps: false,
  dynamicItems: false,
};
