export type SemanticRole = 'UNKNOWN' | 'ACCUMULATOR' | 'COUNTER' | 'FLAG' | 'RUNNING_MAXIMUM' | 'RUNNING_MINIMUM';
export type ContainerRole = 'UNKNOWN' | 'ARRAY' | 'STACK' | 'QUEUE' | 'DEQUE' | 'HEAP';

export type VariableSemanticIdentity = {
  roleScores: Record<SemanticRole, number>;
  primaryRole: SemanticRole;
  containerScores: Record<ContainerRole, number>;
  primaryContainerRole: ContainerRole;
  operations?: {
    rearInsert: boolean;
    frontInsert: boolean;
    rearRemove: boolean;
    frontRemove: boolean;
  };
}

export class SemanticAnalyzer {
  private memory: Record<string, VariableSemanticIdentity> = {};
  private transientComparisons: Record<string, 'MAX_CANDIDATE' | 'MIN_CANDIDATE'> = {};

  /**
   * Analyzes the execution state for a single frame and updates variable semantic classifications.
   * 
   * @param locals The current frame's local variables mapping
   * @param prevLocals The previous frame's local variables mapping
   * @param currentLineCode The raw code string executing on the current frame
   */
  public analyzeFrame(locals: Record<string, any>, prevLocals: Record<string, any>, currentLineCode: string) {
    if (!locals) return;

    this.cleanupMemory(locals);
    this.initializeNewVariables(locals);

    this.observeMutations(locals, prevLocals, currentLineCode);
    this.observeContainerMutations(locals, prevLocals, currentLineCode);
    
    // Clear transient comparisons AFTER mutations have consumed them
    this.transientComparisons = {};
    
    this.observeComparisons(currentLineCode);
    this.observeBooleanTransitions(locals, prevLocals, currentLineCode);
    this.observeAssignments(locals, prevLocals, currentLineCode);

    this.derivePrimaryRoles();
    
    // Internal debugging / auditing
    if (Object.keys(locals).length > 0) {
      console.log("[Semantic Analyzer] Frame Classification:", JSON.parse(JSON.stringify(this.memory)));
    }
  }

  private cleanupMemory(locals: Record<string, any>) {
    for (const k of Object.keys(this.memory)) {
      if (locals[k] === undefined) {
        delete this.memory[k];
      }
    }
  }

  private initializeNewVariables(locals: Record<string, any>) {
    for (const k of Object.keys(locals)) {
      if (!this.memory[k]) {
        this.memory[k] = {
          roleScores: {
            UNKNOWN: 0,
            ACCUMULATOR: 0,
            COUNTER: 0,
            FLAG: 0,
            RUNNING_MAXIMUM: 0,
            RUNNING_MINIMUM: 0
          },
          primaryRole: 'UNKNOWN',
          containerScores: {
            UNKNOWN: 0,
            ARRAY: 0,
            STACK: 0,
            QUEUE: 0,
            DEQUE: 0,
            HEAP: 0
          },
          primaryContainerRole: 'UNKNOWN',
          operations: {
            rearInsert: false,
            frontInsert: false,
            rearRemove: false,
            frontRemove: false
          }
        };
      }
    }
  }

  private observeMutations(locals: Record<string, any>, prevLocals: Record<string, any>, currentLineCode: string) {
    for (const [k, v] of Object.entries(locals)) {
      const prevV = prevLocals[k];
      
      // Value-based mutation observations
      if ((typeof v === 'string' && !v.startsWith('<')) || typeof v === 'number') {
        const numVal = typeof v === 'number' ? v : parseInt(v as string, 10);
        const prevNumVal = prevV === undefined ? undefined : (typeof prevV === 'number' ? prevV : parseInt(prevV as string, 10));
        
        if (!isNaN(numVal) && prevNumVal !== undefined && !isNaN(prevNumVal)) {
          const delta = numVal - prevNumVal;
          if (delta !== 0) {
            // Mutation occurred!
            if (Math.abs(delta) === 1) {
              // Exact +/- 1 indicates Counter behavior
              this.memory[k].roleScores.COUNTER += 50;
              this.memory[k].roleScores.ACCUMULATOR += 10; // Weak accumulator overlap
            } else {
              // Arbitrary delta indicates Accumulator behavior
              this.memory[k].roleScores.ACCUMULATOR += 50;
            }

            // Check transient min/max candidates from the previous frame
            if (delta > 0 && this.transientComparisons[k] === 'MAX_CANDIDATE') {
              this.memory[k].roleScores.RUNNING_MAXIMUM += 80;
            }
            if (delta < 0 && this.transientComparisons[k] === 'MIN_CANDIDATE') {
              this.memory[k].roleScores.RUNNING_MINIMUM += 80;
            }
          }
        }
      }
      
      // Code-based mutation observations (Lexical context)
      if (currentLineCode) {
        // e.g., var += 1 or var += x
        const regexPlusEqual = new RegExp(`\\b${k}\\s*\\+=\\s*([^\\n]+)`, 'g');
        const match = regexPlusEqual.exec(currentLineCode);
        if (match) {
          const incrementStr = match[1].trim();
          if (incrementStr === '1') {
            this.memory[k].roleScores.COUNTER += 20;
          } else {
            this.memory[k].roleScores.ACCUMULATOR += 20;
          }
        }
        
        // e.g., var = var + 1 or var = var + x
        const regexEqualPlus = new RegExp(`\\b${k}\\s*=\\s*\\b${k}\\b\\s*\\+\\s*([^\\n]+)`, 'g');
        const match2 = regexEqualPlus.exec(currentLineCode);
        if (match2) {
          const incrementStr = match2[1].trim();
          if (incrementStr === '1') {
            this.memory[k].roleScores.COUNTER += 20;
          } else {
            this.memory[k].roleScores.ACCUMULATOR += 20;
          }
        }

        // Functional max()/min() assignments
        const regexMax = new RegExp(`\\b${k}\\s*=\\s*max\\([^)]+\\)`, 'g');
        if (regexMax.test(currentLineCode)) {
          this.memory[k].roleScores.RUNNING_MAXIMUM += 30; // Strong lexical evidence
          if (prevV !== undefined && locals[k] > prevV) {
            this.memory[k].roleScores.RUNNING_MAXIMUM += 80; // Definitive mutation
          }
        }
        
        const regexMin = new RegExp(`\\b${k}\\s*=\\s*min\\([^)]+\\)`, 'g');
        if (regexMin.test(currentLineCode)) {
          this.memory[k].roleScores.RUNNING_MINIMUM += 30; // Strong lexical evidence
          if (prevV !== undefined && locals[k] < prevV) {
            this.memory[k].roleScores.RUNNING_MINIMUM += 80; // Definitive mutation
          }
        }
      }
    }
  }

  private observeContainerMutations(locals: Record<string, any>, prevLocals: Record<string, any>, currentLineCode: string) {
    for (const [k, v] of Object.entries(locals)) {
      const prevV = prevLocals[k];

      // Array/List operations detection
      const isCurrentArray = Array.isArray(v);
      const isPrevArray = Array.isArray(prevV);

      if (isCurrentArray && isPrevArray) {
        const curLen = v.length;
        const prevLen = prevV.length;
        
        let prefixMatches = true;
        let suffixMatches = true;
        const minLen = Math.min(curLen, prevLen);

        for (let i = 0; i < minLen; i++) {
          if (v[i] !== prevV[i]) {
            prefixMatches = false;
            break;
          }
        }

        let shiftLeftMatches = true;
        if (curLen === prevLen - 1) {
            for (let i = 0; i < curLen; i++) {
                if (v[i] !== prevV[i+1]) {
                    shiftLeftMatches = false;
                    break;
                }
            }
        } else {
            shiftLeftMatches = false;
        }

        let shiftRightMatches = true;
        if (curLen === prevLen + 1) {
            for (let i = 0; i < prevLen; i++) {
                if (v[i+1] !== prevV[i]) {
                    shiftRightMatches = false;
                    break;
                }
            }
        } else {
            shiftRightMatches = false;
        }

        const ensureOps = () => {
            if (!this.memory[k].operations) {
                this.memory[k].operations = { rearInsert: false, frontInsert: false, rearRemove: false, frontRemove: false };
            }
        };

        // Behavioral Push (REAR INSERT - standard Array growth)
        if (curLen === prevLen + 1 && prefixMatches) {
          this.memory[k].containerScores.ARRAY += 50;
          ensureOps();
          this.memory[k].operations!.rearInsert = true;
        } 
        // Behavioral Pop (STACK / REAR REMOVE)
        else if (curLen === prevLen - 1 && prefixMatches) {
          this.memory[k].containerScores.STACK += 300;
          this.memory[k].containerScores.QUEUE -= 50;
          ensureOps();
          this.memory[k].operations!.rearRemove = true;
        }
        // Behavioral Dequeue (QUEUE / FRONT REMOVE)
        else if (shiftLeftMatches) {
          this.memory[k].containerScores.QUEUE += 50;
          this.memory[k].containerScores.STACK -= 50;
          ensureOps();
          this.memory[k].operations!.frontRemove = true;
        }
        // Behavioral Front Insert (DEQUE / FRONT INSERT)
        else if (shiftRightMatches) {
          this.memory[k].containerScores.QUEUE -= 50;
          this.memory[k].containerScores.STACK -= 50;
          ensureOps();
          this.memory[k].operations!.frontInsert = true;
        }
        // Behavioral Shift / Insertion at front or middle (ARRAY)
        else if (curLen !== prevLen && !prefixMatches) {
          this.memory[k].containerScores.ARRAY += 50;
          this.memory[k].containerScores.STACK -= 20; // Penalize Stack
          this.memory[k].containerScores.QUEUE -= 20; // Penalize Queue
        }

        // DEQUE Composite Scoring
        const ops = this.memory[k].operations;
        if (ops) {
            if ((ops.rearRemove && ops.frontRemove) || (ops.rearInsert && ops.frontInsert)) {
                if (this.memory[k].containerScores.DEQUE < 500) {
                    this.memory[k].containerScores.DEQUE = 500;
                }
            }
        }
        // Identical Length Mutations
        else if (curLen === prevLen) {
          let differences = 0;
          let lastDiffIndex = -1;
          for (let i = 0; i < curLen; i++) {
            if (v[i] !== prevV[i]) {
              differences++;
              lastDiffIndex = i;
            }
          }

          if (differences > 0) {
            // If only the tail was mutated
            if (differences === 1 && lastDiffIndex === curLen - 1) {
              this.memory[k].containerScores.STACK += 20;
            } else {
              // Mid-array mutations or multiple swaps
              this.memory[k].containerScores.ARRAY += 50;
              this.memory[k].containerScores.STACK -= 20;
            }
          }
        }
      } else if (isCurrentArray && !isPrevArray) {
        // Initialization
        this.memory[k].containerScores.ARRAY += 50;
      }

      // Lexical Clues for Arrays
      if (isCurrentArray && currentLineCode) {
        const line = currentLineCode.trim();
        
        // Lexical iteration
        const regexIter = new RegExp(`\\bfor\\s+.*\\s+in\\s+${k}\\b`);
        const regexRange = new RegExp(`\\bfor\\s+.*\\s+in\\s+range\\s*\\(\\s*len\\s*\\(\\s*${k}\\s*\\)\\s*\\)`);
        
        if (regexIter.test(line) || regexRange.test(line)) {
          this.memory[k].containerScores.ARRAY += 50;
        }

        // Lexical Sort
        if (line.includes(`${k}.sort()`) || line.includes(`sorted(${k})`)) {
          this.memory[k].containerScores.ARRAY += 50;
        }

        // Lexical Stack Hooks
        if (line.includes(`${k}.pop()`) || line.includes(`${k}.pop_back()`)) {
          this.memory[k].containerScores.STACK += 150;
        }
        
        // Front operations (Queue/Deque clues)
        if (line.includes(`${k}.pop(0)`) || line.includes(`${k}.popleft()`)) {
          this.memory[k].containerScores.QUEUE += 20; 
        } else if (line.includes(`${k}.insert(0,`)) {
          this.memory[k].containerScores.ARRAY += 30; 
          this.memory[k].containerScores.STACK -= 30;
          this.memory[k].containerScores.QUEUE -= 30;
        }

        // Tail access
        if (line.includes(`${k}[-1]`) || line.includes(`${k}[len(${k})-1]`)) {
          this.memory[k].containerScores.STACK += 10;
        }

        // Arbitrary indexing
        const regexIndex = new RegExp(`\\b${k}\\[([^\\]]+)\\]`);
        const match = regexIndex.exec(line);
        if (match) {
          const inner = match[1].trim();
          if (inner !== '-1' && !inner.includes(`len(${k})-1`)) {
            // Don't strongly penalize simple indexing (might just be checking bounds), but slightly boost array
            this.memory[k].containerScores.ARRAY += 10;
          }
        }
        
        // HEAP explicit detection
        if (line.includes(`heapq.heappush(${k}`) || 
            line.includes(`heapq.heappop(${k}`) || 
            line.includes(`heapq.heapify(${k}`)) {
          this.memory[k].containerScores.HEAP += 500;
        }
      }
    }
  }

  private observeComparisons(currentLineCode: string) {
    if (!currentLineCode || (!currentLineCode.includes('if ') && !currentLineCode.includes('elif '))) return;

    if (currentLineCode.includes('>')) {
       const parts = currentLineCode.split('>');
       if (parts.length >= 2) {
         const left = parts[0];
         const right = parts[1];
         for (const k of Object.keys(this.memory)) {
           const regex = new RegExp(`\\b${k}\\b`);
           if (regex.test(left)) this.transientComparisons[k] = 'MIN_CANDIDATE';
           if (regex.test(right)) this.transientComparisons[k] = 'MAX_CANDIDATE';
         }
       }
    } else if (currentLineCode.includes('<')) {
       const parts = currentLineCode.split('<');
       if (parts.length >= 2) {
         const left = parts[0];
         const right = parts[1];
         for (const k of Object.keys(this.memory)) {
           const regex = new RegExp(`\\b${k}\\b`);
           if (regex.test(left)) this.transientComparisons[k] = 'MAX_CANDIDATE';
           if (regex.test(right)) this.transientComparisons[k] = 'MIN_CANDIDATE';
         }
       }
    }
  }

  private observeBooleanTransitions(locals: Record<string, any>, prevLocals: Record<string, any>, currentLineCode: string) {
    for (const [k, v] of Object.entries(locals)) {
      const isBoolStr = v === 'True' || v === 'False';
      const prevV = prevLocals[k];
      
      if (isBoolStr) {
        // Being initialized to a boolean is weak evidence of a FLAG
        if (prevV === undefined) {
          this.memory[k].roleScores.FLAG += 10;
        } else if (v !== prevV) {
          // Transitioning between booleans is definitive evidence of a FLAG
          this.memory[k].roleScores.FLAG += 50;
        }
      }
    }
  }

  private observeAssignments(locals: Record<string, any>, prevLocals: Record<string, any>, currentLineCode: string) {
    // Reserved for future assignment observation (e.g. TARGET initialization)
  }

  private derivePrimaryRoles() {
    for (const [k, identity] of Object.entries(this.memory)) {
      // 1. Primitive Role Derivation
      let maxScore = -1;
      let primaryRole: SemanticRole = 'UNKNOWN';
      
      for (const [role, score] of Object.entries(identity.roleScores)) {
        if (score > maxScore && score >= 20) { // Classification threshold
          maxScore = score;
          primaryRole = role as SemanticRole;
        }
      }
      identity.primaryRole = primaryRole;

      // 2. Container Role Derivation (Sticky Hysteresis)
      let reigningRole = identity.primaryContainerRole;
      let reigningScore = identity.containerScores[reigningRole] || 0;

      for (const [role, score] of Object.entries(identity.containerScores)) {
        if (role === reigningRole) continue;
        
        // To dethrone the established role, the challenger must beat it by an overwhelming margin
        const marginToDethrone = reigningRole === 'UNKNOWN' ? 0 : (reigningRole === 'DEQUE' || reigningRole === 'HEAP' ? Infinity : 100);
        
        if (score > reigningScore + marginToDethrone && score >= 40) {
          reigningRole = role as ContainerRole;
          reigningScore = score;
        }
      }
      identity.primaryContainerRole = reigningRole;
    }
  }

  public getMemory() {
    return this.memory;
  }
}
