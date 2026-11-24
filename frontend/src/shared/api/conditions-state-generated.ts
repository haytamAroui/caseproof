/* Generated from Python ConditionsStateView. Do not edit. */

/**
 * @maxItems 64
 */
export type Evidence = string[];
export type Id = string;
export type Label = string;
/**
 * @maxItems 32
 */
export type Pieces = string[];
export type Question = string;
/**
 * @maxItems 64
 */
export type Trigger = string[];
/**
 * @maxItems 50
 */
export type Conditions = ConditionInput[];
export type Note = string;
export type Revision = number;
export type Schema = "caseproof-conditions-state-v1";
export type SpecSha256 = string | null;

export interface ConditionsStateView {
  conditions: Conditions;
  note: Note;
  revision: Revision;
  schema: Schema;
  spec_sha256?: SpecSha256;
}
/**
 * One lawyer condition: literal trigger words in the brief, literal words to find in the pieces.
 */
export interface ConditionInput {
  evidence: Evidence;
  id: Id;
  label: Label;
  pieces: Pieces;
  question: Question;
  trigger: Trigger;
}
