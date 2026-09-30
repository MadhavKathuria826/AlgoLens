/**
 * Universal AlgoLens Event Protocol Validator & Ingestion Engine (Milestone 8)
 * Validates inbound event streams received from the backend language producers.
 * Enforces schema integrity, monotonic sequence ordering, and error boundaries.
 */

import { AlgoLensEvent, EventValidationResult, EventStreamMetadata } from '@/types/events';

export function validateAlgoLensEvents(rawEvents: any): EventValidationResult {
  if (!rawEvents) {
    return {
      valid: true,
      events: [],
      metadata: { eventCount: 0, hasTermination: false, isTruncated: false }
    };
  }

  if (!Array.isArray(rawEvents)) {
    return {
      valid: false,
      events: [],
      error: 'Event payload must be a JSON array of AlgoLensEvent objects.'
    };
  }

  let prevSeq = -1;
  let hasTermination = false;
  let isTruncated = false;
  const validatedEvents: AlgoLensEvent[] = [];

  for (let i = 0; i < rawEvents.length; i++) {
    const ev = rawEvents[i];

    if (!ev || typeof ev !== 'object') {
      return {
        valid: false,
        events: validatedEvents,
        error: `Malformed event at index ${i}: expected object, got ${typeof ev}`
      };
    }

    if (typeof ev.seq !== 'number' || typeof ev.line !== 'number' || typeof ev.event_type !== 'string') {
      return {
        valid: false,
        events: validatedEvents,
        error: `Invalid event header at index ${i}: seq, line, and event_type are required.`
      };
    }

    if (ev.payload === undefined || ev.payload === null || typeof ev.payload !== 'object') {
      return {
        valid: false,
        events: validatedEvents,
        error: `Missing or invalid payload at index ${i} (event_type: ${ev.event_type})`
      };
    }

    // Sequence numbers must be strictly non-decreasing
    if (ev.seq < prevSeq) {
      return {
        valid: false,
        events: validatedEvents,
        error: `Non-monotonic event sequence at index ${i}: previous ${prevSeq}, current ${ev.seq}`
      };
    }
    prevSeq = ev.seq;

    if (ev.event_type === 'PROG_END') {
      hasTermination = true;
    } else if (ev.event_type === 'TRACE_TRUNCATED') {
      isTruncated = true;
    }

    validatedEvents.push(ev as AlgoLensEvent);
  }

  const metadata: EventStreamMetadata = {
    eventCount: validatedEvents.length,
    hasTermination,
    isTruncated
  };

  return {
    valid: true,
    events: validatedEvents,
    metadata
  };
}
