"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SemanticAnalyzer = void 0;
var SemanticAnalyzer = /** @class */ (function () {
    function SemanticAnalyzer() {
        this.memory = {};
        this.transientComparisons = {};
    }
    /**
     * Analyzes the execution state for a single frame and updates variable semantic classifications.
     *
     * @param locals The current frame's local variables mapping
     * @param prevLocals The previous frame's local variables mapping
     * @param currentLineCode The raw code string executing on the current frame
     */
    SemanticAnalyzer.prototype.analyzeFrame = function (locals, prevLocals, currentLineCode) {
        if (!locals)
            return;
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
    };
    SemanticAnalyzer.prototype.cleanupMemory = function (locals) {
        for (var _i = 0, _a = Object.keys(this.memory); _i < _a.length; _i++) {
            var k = _a[_i];
            if (locals[k] === undefined) {
                delete this.memory[k];
            }
        }
    };
    SemanticAnalyzer.prototype.initializeNewVariables = function (locals) {
        for (var _i = 0, _a = Object.keys(locals); _i < _a.length; _i++) {
            var k = _a[_i];
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
                        DEQUE: 0
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
    };
    SemanticAnalyzer.prototype.observeMutations = function (locals, prevLocals, currentLineCode) {
        for (var _i = 0, _a = Object.entries(locals); _i < _a.length; _i++) {
            var _b = _a[_i], k = _b[0], v = _b[1];
            var prevV = prevLocals[k];
            // Value-based mutation observations
            if ((typeof v === 'string' && !v.startsWith('<')) || typeof v === 'number') {
                var numVal = typeof v === 'number' ? v : parseInt(v, 10);
                var prevNumVal = prevV === undefined ? undefined : (typeof prevV === 'number' ? prevV : parseInt(prevV, 10));
                if (!isNaN(numVal) && prevNumVal !== undefined && !isNaN(prevNumVal)) {
                    var delta = numVal - prevNumVal;
                    if (delta !== 0) {
                        // Mutation occurred!
                        if (Math.abs(delta) === 1) {
                            // Exact +/- 1 indicates Counter behavior
                            this.memory[k].roleScores.COUNTER += 50;
                            this.memory[k].roleScores.ACCUMULATOR += 10; // Weak accumulator overlap
                        }
                        else {
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
                var regexPlusEqual = new RegExp("\\b".concat(k, "\\s*\\+=\\s*([^\\n]+)"), 'g');
                var match = regexPlusEqual.exec(currentLineCode);
                if (match) {
                    var incrementStr = match[1].trim();
                    if (incrementStr === '1') {
                        this.memory[k].roleScores.COUNTER += 20;
                    }
                    else {
                        this.memory[k].roleScores.ACCUMULATOR += 20;
                    }
                }
                // e.g., var = var + 1 or var = var + x
                var regexEqualPlus = new RegExp("\\b".concat(k, "\\s*=\\s*\\b").concat(k, "\\b\\s*\\+\\s*([^\\n]+)"), 'g');
                var match2 = regexEqualPlus.exec(currentLineCode);
                if (match2) {
                    var incrementStr = match2[1].trim();
                    if (incrementStr === '1') {
                        this.memory[k].roleScores.COUNTER += 20;
                    }
                    else {
                        this.memory[k].roleScores.ACCUMULATOR += 20;
                    }
                }
                // Functional max()/min() assignments
                var regexMax = new RegExp("\\b".concat(k, "\\s*=\\s*max\\([^)]+\\)"), 'g');
                if (regexMax.test(currentLineCode)) {
                    this.memory[k].roleScores.RUNNING_MAXIMUM += 30; // Strong lexical evidence
                    if (prevV !== undefined && locals[k] > prevV) {
                        this.memory[k].roleScores.RUNNING_MAXIMUM += 80; // Definitive mutation
                    }
                }
                var regexMin = new RegExp("\\b".concat(k, "\\s*=\\s*min\\([^)]+\\)"), 'g');
                if (regexMin.test(currentLineCode)) {
                    this.memory[k].roleScores.RUNNING_MINIMUM += 30; // Strong lexical evidence
                    if (prevV !== undefined && locals[k] < prevV) {
                        this.memory[k].roleScores.RUNNING_MINIMUM += 80; // Definitive mutation
                    }
                }
            }
        }
    };
    SemanticAnalyzer.prototype.observeContainerMutations = function (locals, prevLocals, currentLineCode) {
        var _this = this;
        var _loop_1 = function (k, v) {
            var prevV = prevLocals[k];
            // Array/List operations detection
            var isCurrentArray = Array.isArray(v);
            var isPrevArray = Array.isArray(prevV);
            if (isCurrentArray && isPrevArray) {
                var curLen = v.length;
                var prevLen = prevV.length;
                var prefixMatches = true;
                var suffixMatches = true;
                var minLen = Math.min(curLen, prevLen);
                for (var i = 0; i < minLen; i++) {
                    if (v[i] !== prevV[i]) {
                        prefixMatches = false;
                        break;
                    }
                }
                var shiftLeftMatches = true;
                if (curLen === prevLen - 1) {
                    for (var i = 0; i < curLen; i++) {
                        if (v[i] !== prevV[i + 1]) {
                            shiftLeftMatches = false;
                            break;
                        }
                    }
                }
                else {
                    shiftLeftMatches = false;
                }
                var shiftRightMatches = true;
                if (curLen === prevLen + 1) {
                    for (var i = 0; i < prevLen; i++) {
                        if (v[i + 1] !== prevV[i]) {
                            shiftRightMatches = false;
                            break;
                        }
                    }
                }
                else {
                    shiftRightMatches = false;
                }
                var ensureOps = function () {
                    if (!_this.memory[k].operations) {
                        _this.memory[k].operations = { rearInsert: false, frontInsert: false, rearRemove: false, frontRemove: false };
                    }
                };
                // Behavioral Push (STACK / QUEUE Enqueue / REAR INSERT)
                if (curLen === prevLen + 1 && prefixMatches) {
                    this_1.memory[k].containerScores.STACK += 50;
                    this_1.memory[k].containerScores.QUEUE += 50;
                    ensureOps();
                    this_1.memory[k].operations.rearInsert = true;
                }
                // Behavioral Pop (STACK / REAR REMOVE)
                else if (curLen === prevLen - 1 && prefixMatches) {
                    this_1.memory[k].containerScores.STACK += 50;
                    this_1.memory[k].containerScores.QUEUE -= 50;
                    ensureOps();
                    this_1.memory[k].operations.rearRemove = true;
                }
                // Behavioral Dequeue (QUEUE / FRONT REMOVE)
                else if (shiftLeftMatches) {
                    this_1.memory[k].containerScores.QUEUE += 50;
                    this_1.memory[k].containerScores.STACK -= 50;
                    ensureOps();
                    this_1.memory[k].operations.frontRemove = true;
                }
                // Behavioral Front Insert (DEQUE / FRONT INSERT)
                else if (shiftRightMatches) {
                    this_1.memory[k].containerScores.QUEUE -= 50;
                    this_1.memory[k].containerScores.STACK -= 50;
                    ensureOps();
                    this_1.memory[k].operations.frontInsert = true;
                }
                // Behavioral Shift / Insertion at front or middle (ARRAY)
                else if (curLen !== prevLen && !prefixMatches) {
                    this_1.memory[k].containerScores.ARRAY += 50;
                    this_1.memory[k].containerScores.STACK -= 20; // Penalize Stack
                    this_1.memory[k].containerScores.QUEUE -= 20; // Penalize Queue
                }
                // DEQUE Composite Scoring
                var ops = this_1.memory[k].operations;
                if (ops) {
                    if ((ops.rearRemove && ops.frontRemove) || (ops.rearInsert && ops.frontInsert)) {
                        if (this_1.memory[k].containerScores.DEQUE < 500) {
                            this_1.memory[k].containerScores.DEQUE = 500;
                        }
                    }
                }
                // Identical Length Mutations
                else if (curLen === prevLen) {
                    var differences = 0;
                    var lastDiffIndex = -1;
                    for (var i = 0; i < curLen; i++) {
                        if (v[i] !== prevV[i]) {
                            differences++;
                            lastDiffIndex = i;
                        }
                    }
                    if (differences > 0) {
                        // If only the tail was mutated
                        if (differences === 1 && lastDiffIndex === curLen - 1) {
                            this_1.memory[k].containerScores.STACK += 20;
                        }
                        else {
                            // Mid-array mutations or multiple swaps
                            this_1.memory[k].containerScores.ARRAY += 50;
                            this_1.memory[k].containerScores.STACK -= 20;
                        }
                    }
                }
            }
            else if (isCurrentArray && !isPrevArray) {
                // Initialization
                this_1.memory[k].containerScores.ARRAY += 10;
            }
            // Lexical Clues for Arrays
            if (isCurrentArray && currentLineCode) {
                var line = currentLineCode.trim();
                // Lexical iteration
                var regexIter = new RegExp("\\bfor\\s+.*\\s+in\\s+".concat(k, "\\b"));
                var regexRange = new RegExp("\\bfor\\s+.*\\s+in\\s+range\\s*\\(\\s*len\\s*\\(\\s*".concat(k, "\\s*\\)\\s*\\)"));
                if (regexIter.test(line) || regexRange.test(line)) {
                    this_1.memory[k].containerScores.ARRAY += 50;
                }
                // Lexical Sort
                if (line.includes("".concat(k, ".sort()")) || line.includes("sorted(".concat(k, ")"))) {
                    this_1.memory[k].containerScores.ARRAY += 50;
                }
                // Lexical Stack Hooks (weak evidence)
                if (line.includes("".concat(k, ".append("))) {
                    this_1.memory[k].containerScores.STACK += 10;
                    this_1.memory[k].containerScores.QUEUE += 10;
                }
                if (line.includes("".concat(k, ".pop()"))) {
                    this_1.memory[k].containerScores.STACK += 10;
                }
                // Front operations (Queue/Deque clues)
                if (line.includes("".concat(k, ".pop(0)")) || line.includes("".concat(k, ".popleft()"))) {
                    this_1.memory[k].containerScores.QUEUE += 20;
                }
                else if (line.includes("".concat(k, ".insert(0,"))) {
                    this_1.memory[k].containerScores.ARRAY += 30;
                    this_1.memory[k].containerScores.STACK -= 30;
                    this_1.memory[k].containerScores.QUEUE -= 30;
                }
                // Tail access
                if (line.includes("".concat(k, "[-1]")) || line.includes("".concat(k, "[len(").concat(k, ")-1]"))) {
                    this_1.memory[k].containerScores.STACK += 10;
                }
                // Arbitrary indexing
                var regexIndex = new RegExp("\\b".concat(k, "\\[([^\\]]+)\\]"));
                var match = regexIndex.exec(line);
                if (match) {
                    var inner = match[1].trim();
                    if (inner !== '-1' && !inner.includes("len(".concat(k, ")-1"))) {
                        // Don't strongly penalize simple indexing (might just be checking bounds), but slightly boost array
                        this_1.memory[k].containerScores.ARRAY += 10;
                    }
                }
            }
        };
        var this_1 = this;
        for (var _i = 0, _a = Object.entries(locals); _i < _a.length; _i++) {
            var _b = _a[_i], k = _b[0], v = _b[1];
            _loop_1(k, v);
        }
    };
    SemanticAnalyzer.prototype.observeComparisons = function (currentLineCode) {
        if (!currentLineCode || (!currentLineCode.includes('if ') && !currentLineCode.includes('elif ')))
            return;
        if (currentLineCode.includes('>')) {
            var parts = currentLineCode.split('>');
            if (parts.length >= 2) {
                var left = parts[0];
                var right = parts[1];
                for (var _i = 0, _a = Object.keys(this.memory); _i < _a.length; _i++) {
                    var k = _a[_i];
                    var regex = new RegExp("\\b".concat(k, "\\b"));
                    if (regex.test(left))
                        this.transientComparisons[k] = 'MIN_CANDIDATE';
                    if (regex.test(right))
                        this.transientComparisons[k] = 'MAX_CANDIDATE';
                }
            }
        }
        else if (currentLineCode.includes('<')) {
            var parts = currentLineCode.split('<');
            if (parts.length >= 2) {
                var left = parts[0];
                var right = parts[1];
                for (var _b = 0, _c = Object.keys(this.memory); _b < _c.length; _b++) {
                    var k = _c[_b];
                    var regex = new RegExp("\\b".concat(k, "\\b"));
                    if (regex.test(left))
                        this.transientComparisons[k] = 'MAX_CANDIDATE';
                    if (regex.test(right))
                        this.transientComparisons[k] = 'MIN_CANDIDATE';
                }
            }
        }
    };
    SemanticAnalyzer.prototype.observeBooleanTransitions = function (locals, prevLocals, currentLineCode) {
        for (var _i = 0, _a = Object.entries(locals); _i < _a.length; _i++) {
            var _b = _a[_i], k = _b[0], v = _b[1];
            var isBoolStr = v === 'True' || v === 'False';
            var prevV = prevLocals[k];
            if (isBoolStr) {
                // Being initialized to a boolean is weak evidence of a FLAG
                if (prevV === undefined) {
                    this.memory[k].roleScores.FLAG += 10;
                }
                else if (v !== prevV) {
                    // Transitioning between booleans is definitive evidence of a FLAG
                    this.memory[k].roleScores.FLAG += 50;
                }
            }
        }
    };
    SemanticAnalyzer.prototype.observeAssignments = function (locals, prevLocals, currentLineCode) {
        // Reserved for future assignment observation (e.g. TARGET initialization)
    };
    SemanticAnalyzer.prototype.derivePrimaryRoles = function () {
        for (var _i = 0, _a = Object.entries(this.memory); _i < _a.length; _i++) {
            var _b = _a[_i], k = _b[0], identity = _b[1];
            // 1. Primitive Role Derivation
            var maxScore = -1;
            var primaryRole = 'UNKNOWN';
            for (var _c = 0, _d = Object.entries(identity.roleScores); _c < _d.length; _c++) {
                var _e = _d[_c], role = _e[0], score = _e[1];
                if (score > maxScore && score >= 20) { // Classification threshold
                    maxScore = score;
                    primaryRole = role;
                }
            }
            identity.primaryRole = primaryRole;
            // 2. Container Role Derivation (Sticky Hysteresis)
            var reigningRole = identity.primaryContainerRole;
            var reigningScore = identity.containerScores[reigningRole] || 0;
            for (var _f = 0, _g = Object.entries(identity.containerScores); _f < _g.length; _f++) {
                var _h = _g[_f], role = _h[0], score = _h[1];
                if (role === reigningRole)
                    continue;
                // To dethrone the established role, the challenger must beat it by an overwhelming margin
                var marginToDethrone = reigningRole === 'UNKNOWN' ? 0 : (reigningRole === 'DEQUE' ? Infinity : 100);
                if (score > reigningScore + marginToDethrone && score >= 40) {
                    reigningRole = role;
                    reigningScore = score;
                }
            }
            identity.primaryContainerRole = reigningRole;
        }
    };
    SemanticAnalyzer.prototype.getMemory = function () {
        return this.memory;
    };
    return SemanticAnalyzer;
}());
exports.SemanticAnalyzer = SemanticAnalyzer;
