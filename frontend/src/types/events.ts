/**
 * Universal AlgoLens Event Protocol TypeScript Definitions (Milestone 8)
 * Standardized schema for execution events emitted by language producers (C++, Python).
 */

export interface UniversalValuePrimitive {
  kind: 'primitive';
  type_name: string;
  value: any;
}

export interface UniversalValueObjectRef {
  kind: 'object_ref';
  object_id: string;
}

export interface UniversalValueNullRef {
  kind: 'null_ref';
}

export interface UniversalValueDanglingRef {
  kind: 'dangling_ref';
  last_known_object_id: string;
}

export interface UniversalValueUninitialized {
  kind: 'uninitialized';
}

export type UniversalValue =
  | UniversalValuePrimitive
  | UniversalValueObjectRef
  | UniversalValueNullRef
  | UniversalValueDanglingRef
  | UniversalValueUninitialized;

export interface AlgoLensEvent {
  seq: number;
  line: number;
  event_type: string;
  payload: Record<string, any>;
  frame_id?: string;
  scope_id?: string;
  timestamp_ns?: number;
}

export interface EventStreamMetadata {
  eventCount: number;
  hasTermination: boolean;
  isTruncated: boolean;
  producerLanguage?: string;
}

export interface EventValidationResult {
  valid: boolean;
  events: AlgoLensEvent[];
  metadata?: EventStreamMetadata;
  error?: string;
}
