"""Clocked persistent RED2 core built on RED2_ABI_V1 / RED2_MEMORY_V1.

The processor intentionally exposes architectural checkpoints only after a
FETCH -> EXECUTE -> COMMIT sequence.  More complex closure/subgraph, primitive,
recursive-block and equality transitions are added by later implementation
slices; encountering one of those paths here produces a deterministic hardware
fault instead of approximating Python behavior.
"""

from pypeline_red2 import red2_stepper as abi
from red2_engine.pipelinec_vectors import EncodedArchitecturalState

RED2_CORE_V1 = 1
RED2_CLOSURES_V1 = 1
RED2_PRIM_SEQ_V1 = 1
RED2_SCALARS_V1 = 1
RED2_LAZY_V1 = 1
RED2_RECURSIVE_V1 = 1
RED2_PURE_V1 = 1
RED2_QUANTUM_V1 = 1
RED2_HOSTCALL_V1 = 1
RED2_PROGRAMS_V1 = 1

SCALAR_OP_NONE = 0
SCALAR_OP_DEC = 1
SCALAR_OP_INC = 2
SCALAR_OP_NEGATE = 3
SCALAR_OP_ABS = 4
SCALAR_OP_FLOOR = 5
SCALAR_OP_CEILING = 6
SCALAR_OP_EVEN = 7
SCALAR_OP_NULL = 8
SCALAR_OP_NOT = 9
SCALAR_OP_INTEGER_P = 10
SCALAR_OP_FLOAT_P = 11
SCALAR_OP_CHAR_P = 12
SCALAR_OP_SYMBOL_P = 13
SCALAR_OP_ADD = 14
SCALAR_OP_SUB = 15
SCALAR_OP_MUL = 16
SCALAR_OP_DIV = 17
SCALAR_OP_LT = 18
SCALAR_OP_GT = 19
SCALAR_OP_LE = 20
SCALAR_OP_GE = 21
SCALAR_OP_EQ = 22
SCALAR_OP_EXPT = 23
SCALAR_OP_MAX = 24
SCALAR_OP_MIN = 25
SCALAR_OP_MOD = 26

PRIM0_ROLE_PASSIVE = 0
PRIM0_ROLE_IF = 1
PRIM0_ROLE_IO_SEQUENCE = 2
PRIM0_ROLE_IO_BIND = PRIM0_ROLE_IO_SEQUENCE
PRIM0_ROLE_DEFERRED = 3
PRIM0_ROLE_Y = 4
PRIM0_ROLE_IO_THEN = 5
PRIM0_ROLE_IO_RETURN = 6

MICRO_FETCH = 0
MICRO_EXECUTE = 1
MICRO_COMMIT = 2
MICRO_FAULT = 3
MICRO_TASK4 = 4

TASK4_NONE = 0
TASK4_JOIN = 1
TASK4_VAR = 2
TASK4_APP_VAR = 3
TASK4_EP = 4
TASK4_IF = 5
TASK4_RBLOCK = 6
TASK4_RUP = 7
TASK4_RECP = 8
TASK4_STRUCT = 9
TASK4_EQUALITY = 10
TASK4_QUANTUM = 11
TASK4_IO = 12

TASK4_COPY_MEMORY = 100
TASK4_COPY_CONTROL = 101
TASK4_JOIN_INIT = 1
TASK4_JOIN_FIND_FRAME = 2
TASK4_JOIN_PUBLISH = 3
TASK4_JOIN_FINISH = 4
TASK4_JOIN_RBLOCK_PHI = 5
TASK4_VAR_LOOKUP = 10
TASK4_VAR_REDEX = 11
TASK4_VAR_CHASE = 12
TASK4_APP_VAR_LOOKUP = 13
TASK4_APP_VAR_REDEX = 14
TASK4_EP_FORWARD = 15
TASK4_EP_CHASE = 16
TASK4_EP_FINISH = 17
TASK4_IF_FIRE = 30
TASK4_IF_EP_CHASE = 31
TASK4_RBLOCK_EXEC = 40
TASK4_RUP_INIT = 41
TASK4_RUP_SCAN = 42
TASK4_RUP_ZERO_PUSH = 43
TASK4_RECP_EXEC = 44
TASK4_RECP_RECON_SCAN = 45
TASK4_RECP_RECON_MARKER = 46
TASK4_RECP_RECON_UBV = 47
TASK4_RECP_RECON_COPY = 48
TASK4_RECP_RECON_PATH = 49
TASK4_RECP_RECON_FINISH = 50
TASK4_STRUCT_EXEC = 51
TASK4_STRUCT_SELECTOR_FIRE = 52
TASK4_STRUCT_COPY_SCAN = 53
TASK4_STRUCT_COPY_WRITE = 54
TASK4_STRUCT_SELECTOR_RESULT = 55
TASK4_STRUCT_PROMOTE_MATERIALIZE = 56
TASK4_STRUCT_PROMOTE_WRITE = 57
TASK4_STRUCT_PROMOTE_CLEAR = 58
TASK4_EQUALITY_FIRE = 60
TASK4_EQUALITY_CHILD_INIT = 61
TASK4_EQUALITY_DECOMPOSE = 62
TASK4_EQUALITY_STRUCT_LEFT = 63
TASK4_EQUALITY_STRUCT_RIGHT = 64
TASK4_EQUALITY_APP_LEFT = 65
TASK4_EQUALITY_APP_RIGHT = 66
TASK4_EQUALITY_LAMBDA = 67
TASK4_EQUALITY_BUILD_TASK = 68
TASK4_EQUALITY_BUILD_TRUE = 69
TASK4_EQUALITY_BUILD_FALSE = 70
TASK4_EQUALITY_BUILD_IF = 71
TASK4_EQUALITY_BUILD_JOIN = 72
TASK4_EQUALITY_CONTINUE = 73
TASK4_EQUALITY_IF_FIRE = 74
TASK4_QUANTUM_INIT = 80
TASK4_QUANTUM_MATERIALIZE = 81
TASK4_QUANTUM_CLEAR_MEMORY = 82
TASK4_QUANTUM_WRITE_MEMORY = 83
TASK4_QUANTUM_CLEAR_CONTROL = 84
TASK4_QUANTUM_FINISH = 85
TASK4_IO_FIRE = 90

TASK4_PUB_GRAPH = 1
TASK4_PUB_ROOT_DONE = 2
TASK4_PUB_APP_SCAN = 3
TASK4_PUB_APP_REWRITE = 4
TASK4_PUB_APP_OPERATOR_DONE = 5
TASK4_PUB_LAMBDA_SCAN = 6
TASK4_PUB_LAMBDA_DONE = 7
TASK4_PUB_EP_CHASE = 8
TASK4_PUB_EP_CLOSURE_DONE = 9
TASK4_PUB_CLOSURE = 10
TASK4_PUB_CLOSURE_WRITE = 11
TASK4_PUB_RBLOCK_SCAN = 12
TASK4_PUB_RBLOCK_BINDING_DONE = 13
TASK4_PUB_RBLOCK_BODY_DONE = 14
TASK4_PUB_STRUCT_SCAN = 15
TASK4_MAT_GRAPH = 20
TASK4_MAT_LEAVE = 21
TASK4_MAT_APP_SCAN = 22
TASK4_MAT_APP_PROCESS = 23
TASK4_MAT_LAMBDA_SCAN = 24
TASK4_MAT_LOOKUP = 25
TASK4_MAT_ENV_CHASE = 26
TASK4_MAT_CLOSURE = 27
TASK4_MAT_REHEAD = 28
TASK4_MAT_VISIT_SCAN = 29
TASK4_PUB_REC = 30
TASK4_PUB_REC_SCAN = 31
TASK4_PUB_REC_BINDINGS = 32
TASK4_PUB_REC_WRITE = 33
TASK4_PUB_REC_RW_GRAPH = 34
TASK4_PUB_REC_RW_VISIT_SCAN = 35
TASK4_PUB_REC_RW_LEAVE = 36
TASK4_PUB_REC_RW_APP_SCAN = 37
TASK4_PUB_REC_RW_LAMBDA_SCAN = 38
TASK4_PUB_REC_RW_RBLOCK = 39
TASK4_PUB_REC_RW_EP_CHASE = 40
TASK4_PUB_REC_RW_STRUCT = 41
TASK4_MAT_STRUCT_SCAN = 42
TASK4_MAT_STRUCT_PROCESS = 43
TASK10_GRAPH = 44
TASK10_VISIT_SCAN = 45
TASK10_LEAVE = 46
TASK10_POINTER = 47
TASK10_POINTER_DONE = 48
TASK10_APP_SCAN = 49
TASK10_APP_PROCESS = 50
TASK10_APP_POINTER_DONE = 51
TASK10_STRUCT_SCAN = 52
TASK10_STRUCT_PROCESS = 53
TASK10_STRUCT_POINTER_DONE = 54
TASK10_LAMBDA_SCAN = 55
TASK10_RBLOCK_SCAN = 56
TASK10_RBLOCK_PROCESS = 57


class Red2Processor:
    """Persistent clocked RED2 architectural state plus non-architectural microstate."""

    def __init__(
        self,
        state: EncodedArchitecturalState,
        *,
        prim0_roles: tuple[int, ...] = (),
        scalar_ops: tuple[int, ...] = (),
        host_ops: tuple[int, ...] = (),
        true_literal_id: int = 0,
        false_literal_id: int = 0,
        nil_literal_id: int = 0,
        if_reconstruct_literal_id: int = 0,
        struct_selector_tags: tuple[int, ...] = (),
        struct_selector_offsets: tuple[int, ...] = (),
        struct_selector_result_literal_id: int = 0,
        cons_literal_id: int = 0,
        pair_literal_id: int = 0,
        equality_literal_id: int = 0,
        equal_star_literal_id: int = 0,
        equal_if_literal_id: int = 0,
        equality_continue_literal_id: int = 0,
        equal_stuck_literal_id: int = 0,
        working_memory_limit: int | None = None,
    ) -> None:
        self.memory = list(state.memory)
        self.control_stack = list(state.control_stack)
        self.pc = state.pc
        self.fsp = state.fsp
        self.env = state.env
        self.c = state.c - 1
        self.direction = state.direction
        self.q = state.q
        self.phi = state.phi
        self.free_space = state.free_space
        self.argcnt = state.argcnt - 1
        self.prim_id = state.prim_id
        self.fire = state.fire
        self.s_a = abi.decode_optional_address(state.s_a)
        self.s_d = abi.decode_optional_address(state.s_d)
        self.halted = state.halted
        self.pending_host_op = state.pending_host_op
        self.pending_host_argument = state.pending_host_argument
        self.working_memory_limit = (
            len(self.memory) if working_memory_limit is None else working_memory_limit
        )
        if (
            type(self.working_memory_limit) is not int
            or self.working_memory_limit < 0
            or self.working_memory_limit > len(self.memory)
        ):
            raise ValueError("working_memory_limit outside processor memory")

        self.microstate = MICRO_FETCH
        self.fetched_word = 0
        self.fault = abi.FAULT_NONE
        self.commits = 0
        self.clocks = 0
        self.prim0_roles = prim0_roles
        self.scalar_ops = scalar_ops
        self.host_ops = host_ops
        self.true_literal_id = true_literal_id
        self.false_literal_id = false_literal_id
        self.nil_literal_id = nil_literal_id
        self.if_reconstruct_literal_id = if_reconstruct_literal_id
        self.struct_selector_tags = struct_selector_tags
        self.struct_selector_offsets = struct_selector_offsets
        self.struct_selector_result_literal_id = struct_selector_result_literal_id
        self.cons_literal_id = cons_literal_id
        self.pair_literal_id = pair_literal_id
        self.equality_literal_id = equality_literal_id
        self.equal_star_literal_id = equal_star_literal_id
        self.equal_if_literal_id = equal_if_literal_id
        self.equality_continue_literal_id = equality_continue_literal_id
        self.equal_stuck_literal_id = equal_stuck_literal_id

        # Task 4 publication/EP chase is microcoded over fixed scratch derived
        # from the already-bounded graph/control memories. Architectural RAM and
        # registers remain untouched until the transition reaches commit.
        memory_words = len(self.memory)
        control_words = len(self.control_stack)
        task_words = memory_words * 4 + control_words + 64
        self._task_memory = [0] * memory_words
        self._task_control = [0] * control_words
        self._task_stack_kind = [0] * task_words
        self._task_stack_a = [0] * task_words
        self._task_stack_b = [0] * task_words
        self._task_stack_c = [0] * task_words
        self._task_stack_d = [0] * task_words
        self._task_stack_e = [0] * task_words
        self._task_stack_f = [0] * task_words
        self._task_stack_g = [0] * task_words
        self._task_stack_h = [0] * task_words
        self._task_pub_root_state = [0] * memory_words
        self._task_pub_root_result = [0] * memory_words
        self._task_pub_closure_valid = [0] * memory_words
        self._task_pub_closure_result = [0] * memory_words
        self._task_pub_rec_valid = [0] * memory_words
        self._task_pub_rec_result = [0] * memory_words
        self._task_mat_words = [0] * memory_words
        self._task_mat_valid = [0] * memory_words
        self._task_mat_visit_address = [0] * memory_words
        self._task_mat_visit_environment = [0] * memory_words
        self._task_mat_visit_depth = [0] * memory_words
        self._task_mat_visit_head = [0] * memory_words
        self._task_eq_left_items = [0] * memory_words
        self._task_eq_right_items = [0] * memory_words
        self._task_eq_child_left = [0] * memory_words
        self._task_eq_child_right = [0] * memory_words
        self._task_eq_child_lambdas = [0] * memory_words
        self._task_eq_child_descriptor = [0] * memory_words
        self._task_eq_child_root = [0] * memory_words
        self._task4_active = 0
        self._task4_kind = TASK4_NONE
        self._task4_phase = 0
        self._task_sp = -1
        self._task_mat_count = 0
        self._task_mat_visit_count = 0
        self._task_pc = 0
        self._task_fsp = 0
        self._task_env = 0
        self._task_c = -1
        self._task_direction = 0
        self._task_q = 0
        self._task_phi = 0
        self._task_free_space = 0
        self._task_argcnt = -1
        self._task_prim_id = 0
        self._task_fire = 0
        self._task_s_a = 0
        self._task_s_a_valid = 0
        self._task_s_d = 0
        self._task_s_d_valid = 0
        self._task_halted = 0
        self._task_pending_host_op = 0
        self._task_pending_host_argument = 0
        self._task_parent_address = 0
        self._task_result_address = 0
        self._task_frame_env = 0
        self._task_frame_free_space = 0
        self._task_frame_prim_id = 0
        self._task_frame_fire = 0
        self._task_saved_primitive = 0
        self._task_interval_start = 0
        self._task_interval_stop = 0
        self._task_published_result = 0
        self._task_join_cursor = 0
        self._task_join_count = 0
        self._task_var_index = 0
        self._task_var_address = 0
        self._task_var_remaining = 0
        self._task_var_hops = 0
        self._task_ep_target = 0
        self._task_ep_hops = 0
        self._task_ep_parent = 0
        self._task_if_target = 0
        self._task_if_hops = 0
        self._task_if_false_slot = 0
        self._task_rec_address = 0
        self._task_rec_binding = 0
        self._task_rec_context = 0
        self._task_rec_block = 0
        self._task_rec_count = 0
        self._task_rec_index = 0
        self._task_rec_head = 0
        self._task_rec_selected = 0
        self._task_rec_replacement = 0
        self._task_rec_reverse_join = 0
        self._task_frame_index = -1
        self._task_pub_value = 0
        self._task_copy_index = 0
        self._task_next_phase = 0
        self._task_struct_source = 0
        self._task_struct_cursor = 0
        self._task_struct_destination = 0
        self._task_struct_old_fsp = 0
        self._task_struct_write_index = 0
        self._task_struct_copy_backward = 0
        self._task_struct_copy_charge = 0
        self._task_struct_source_is_lambda = 0
        self._task_eq_left = 0
        self._task_eq_right = 0
        self._task_eq_left_word = 0
        self._task_eq_right_word = 0
        self._task_eq_lambdas = 0
        self._task_eq_descriptor = 0
        self._task_eq_join = 0
        self._task_eq_left_count = 0
        self._task_eq_right_count = 0
        self._task_eq_cursor = 0
        self._task_eq_child_count = 0
        self._task_eq_build_child = 0
        self._task_eq_build_word = 0
        self._task_eq_branch_root = 0
        self._task_eq_false_root = 0
        self._task_eq_true_root = 0
        self._task_eq_result = 0
        self._task_eq_result_known = 0
        self._task_eq_mode = 0
        self._task_quantum_value = 0
        self._task_quantum_cursor = 0
        self._task_quantum_write_index = 0

    def checkpoint(self) -> EncodedArchitecturalState:
        """Return the hardware-visible architectural state at a commit boundary."""
        return EncodedArchitecturalState(
            memory=tuple(self.memory),
            control_stack=tuple(self.control_stack),
            pc=self.pc,
            fsp=self.fsp,
            env=self.env,
            c=self.c + 1,
            direction=self.direction,
            q=self.q,
            phi=self.phi,
            free_space=self.free_space,
            argcnt=self.argcnt + 1,
            prim_id=self.prim_id,
            fire=self.fire,
            s_a=abi.encode_optional_address(self.s_a),
            s_d=abi.encode_optional_address(self.s_d),
            halted=self.halted,
            pending_host_op=self.pending_host_op,
            pending_host_argument=self.pending_host_argument,
        )

    def status(self) -> int:
        """Return the scheduler-visible RED2_ABI_V1 processor status."""
        if self.fault != abi.FAULT_NONE or self.microstate == MICRO_FAULT:
            return abi.STATUS_FAULT
        if self.pending_host_op != abi.HOST_NONE and self.microstate == MICRO_FETCH:
            return abi.STATUS_HOST_CALL
        if self.halted and self.microstate == MICRO_FETCH:
            if self.q == 0:
                return abi.STATUS_QUANTUM_EXHAUSTED
            return abi.STATUS_COMPLETE
        return abi.STATUS_RUNNING

    def run_until_suspend(self, max_clocks: int = 1_000_000) -> int:
        """Run until completion, host suspension, fault, or a halted q=0 residual."""
        if type(max_clocks) is not int or max_clocks < 0:
            raise ValueError("max_clocks must be a non-negative integer")
        current = self.status()
        if current != abi.STATUS_RUNNING:
            return current
        for _ in range(max_clocks):
            self.clock()
            current = self.status()
            if current != abi.STATUS_RUNNING:
                return current
        return abi.STATUS_RUNNING

    def resume_host_call(self, result: int) -> int:
        """Commit one atomic host result into the currently suspended RED2 machine."""
        if (
            self.fault != abi.FAULT_NONE
            or self.microstate != MICRO_FETCH
            or self.halted
            or self.pending_host_op == abi.HOST_NONE
            or self.q <= 0
            or type(result) is not int
            or result < 0
            or result >= (1 << abi.WORD_WIDTH)
            or abi.word_field(result, abi.WORD_VALID_SHIFT, 1) != 1
        ):
            self._fault(abi.FAULT_INVALID_RESUME)
            return self.status()

        opcode = self._opcode(result)
        kind = self._data_kind(result)
        payload = self._payload(result)
        atomic = (
            (opcode == abi.MOP_INT and kind == abi.DATA_SIGNED)
            or (opcode == abi.MOP_FLOAT and kind == abi.DATA_FLOAT64)
            or (
                opcode in (abi.MOP_CHAR, abi.MOP_SYM)
                and kind == abi.DATA_LITERAL_ID
                and 0 < payload <= abi.LITERAL_ID_MAX
            )
        )
        reserved_mask = abi.WORD_MASK ^ ((1 << (abi.WORD_VALID_SHIFT + 1)) - 1)
        definition_valid = self._definition_valid(result)
        definition = self._definition(result)
        if (
            not atomic
            or (result & reserved_mask) != 0
            or self._closure_slot(result) != 0
            or (not definition_valid and definition != 0)
        ):
            self._fault(abi.FAULT_INVALID_RESUME)
            return self.status()

        host_op = self.pending_host_op
        encoded_argument = self.pending_host_argument
        direct = host_op in (abi.HOST_CLOCK, abi.HOST_UART_RX)
        strict = host_op in (abi.HOST_UART_TX, abi.HOST_UART_TX_BYTES)
        if (direct and encoded_argument != 0) or (
            strict
            and (
                type(encoded_argument) is not int
                or encoded_argument <= 0
                or encoded_argument > abi.FRONTIER_MAX
            )
        ) or (not direct and not strict):
            self._fault(abi.FAULT_INVALID_RESUME)
            return self.status()

        argument_address = -1 if direct else encoded_argument - 1
        if strict and (
            argument_address < 0
            or argument_address >= len(self.memory)
            or self.pc != argument_address
        ):
            self._fault(abi.FAULT_INVALID_RESUME)
            return self.status()

        resumed = self._make_word(
            opcode,
            kind,
            payload,
            1,
            self._definition_valid(result),
            self._definition(result),
        )
        if direct:
            destination = self.fsp + 1
            if destination >= self.free_space or destination >= len(self.memory):
                self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                return self.status()
            self.memory[destination] = resumed
            self.fsp = destination
            self.argcnt += 1
            self.q -= 1
            self.pc = self.fsp - 1
            self.direction = abi.DIRECTION_REVERSE
        else:
            self.memory[self.pc] = resumed
            self.fsp = self.pc
            self.q -= 1
            self.pc -= 1

        self.pending_host_op = abi.HOST_NONE
        self.pending_host_argument = 0
        return self.status()

    def recharge_quantum(self, quantum: int, max_clocks: int | None = None) -> int:
        """Refill an exhausted live state or restart a halted bounded residual."""
        if (
            type(quantum) is not int
            or quantum < 0
            or quantum > abi.CONTROL_PAYLOAD_MASK
        ):
            self._fault(abi.FAULT_INVALID_RESUME)
            return self.status()
        if self.pending_host_op != abi.HOST_NONE or self.microstate != MICRO_FETCH:
            self._fault(abi.FAULT_INVALID_RESUME)
            return self.status()
        if not self.halted:
            if self.q != 0:
                self._fault(abi.FAULT_INVALID_RESUME)
                return self.status()
            self.q = quantum
            return self.status()
        self._task4_begin(TASK4_QUANTUM, TASK4_QUANTUM_INIT)
        self._task_quantum_value = quantum
        self.microstate = MICRO_TASK4
        if max_clocks is None:
            max_clocks = self._default_run_to_commit_budget()
        target = self.commits + 1
        for _ in range(max_clocks):
            if self.clock() and self.commits == target:
                return self.status()
            if self.microstate == MICRO_FAULT:
                return self.status()
        return self.status()

    def clock(self) -> bool:
        """Advance one processor clock; return True exactly when a RED2 step commits."""
        self.clocks += 1
        if self.microstate == MICRO_FAULT:
            return False
        if self.microstate == MICRO_FETCH:
            if self.halted or self.pending_host_op != abi.HOST_NONE:
                return False
            if not 0 <= self.pc < len(self.memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return False
            self.fetched_word = self.memory[self.pc]
            if self.fetched_word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return False
            self.microstate = MICRO_EXECUTE
            return False
        if self.microstate == MICRO_EXECUTE:
            self._execute(self.fetched_word)
            if self.fault == abi.FAULT_NONE and self.microstate == MICRO_EXECUTE:
                self.microstate = MICRO_COMMIT
            return False
        if self.microstate == MICRO_TASK4:
            self._task4_clock()
            return False
        if self.microstate == MICRO_COMMIT:
            if self._task4_active:
                self._task4_commit()
            self.commits += 1
            self.microstate = MICRO_FETCH
            return True
        self._fault(abi.FAULT_ILLEGAL_TRANSITION)
        return False

    def _default_run_to_commit_budget(self) -> int:
        """Conservative host-side clock bound for one bounded processor transition."""
        memory_words = len(self.memory)
        control_words = len(self.control_stack)
        # Task 4 materialization may compare each newly active graph node against
        # every active ancestor one comparison per clock.  That bounded search is
        # quadratic in graph RAM size in the worst case; keep the convenience
        # driver above that bound so it cannot manufacture a false liveness stall.
        return memory_words * memory_words * 8 + memory_words * 64 + control_words * 8 + 256

    def run_to_commit(self, max_clocks: int | None = None) -> bool:
        """Clock until one bounded RED2 transition commits or the core faults/stalls."""
        if max_clocks is None:
            max_clocks = self._default_run_to_commit_budget()
        target = self.commits + 1
        clocks = 0
        while clocks < max_clocks:
            if self.clock() and self.commits == target:
                return True
            if self.microstate == MICRO_FAULT:
                return False
            if self.halted and self.microstate != MICRO_COMMIT:
                return False
            clocks += 1
        return False

    def _fault(self, fault: int) -> None:
        self.fault = fault
        self.microstate = MICRO_FAULT

    def _field(self, word: int, shift: int, bits: int) -> int:
        return abi.word_field(word, shift, bits)

    def _opcode(self, word: int) -> int:
        return self._field(word, abi.WORD_OPCODE_SHIFT, abi.WORD_OPCODE_BITS)

    def _head(self, word: int) -> int:
        return self._field(word, abi.WORD_HEAD_SHIFT, 1)

    def _closure_slot(self, word: int) -> int:
        return self._field(word, abi.WORD_CLOSURE_SLOT_SHIFT, 1)

    def _definition_valid(self, word: int) -> int:
        return self._field(word, abi.WORD_DEFINITION_VALID_SHIFT, 1)

    def _definition(self, word: int) -> int:
        return self._field(word, abi.WORD_DEFINITION_SHIFT, abi.WORD_DEFINITION_BITS)

    def _data_kind(self, word: int) -> int:
        return self._field(word, abi.WORD_DATA_KIND_SHIFT, abi.WORD_DATA_KIND_BITS)

    def _payload(self, word: int) -> int:
        return self._field(word, abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS)

    def _signed_data(self, word: int) -> int | None:
        if self._data_kind(word) != abi.DATA_SIGNED:
            return None
        return abi.payload_to_signed(self._payload(word))

    def _make_word(
        self,
        opcode: int,
        data_kind: int,
        payload: int,
        head: int,
        definition_valid: int = 0,
        definition: int = 0,
        closure_slot: int = 0,
    ) -> int:
        return abi.pack_word(
            1,
            opcode,
            data_kind,
            payload,
            head,
            closure_slot,
            definition_valid,
            definition,
        )

    def _clone_word(self, word: int, head: int) -> int:
        return self._make_word(
            self._opcode(word),
            self._data_kind(word),
            self._payload(word),
            head,
            self._definition_valid(word),
            self._definition(word),
            self._closure_slot(word),
        )

    def _push_result(self, word: int) -> bool:
        fault, fsp, _ = abi.red2_push_graph(
            self.memory, self.fsp, self.free_space, word
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self.fsp = fsp
        self.argcnt += 1
        return True

    def _push_control_path(self, path: int) -> bool:
        entry = abi.pack_control_entry(abi.CONTROL_ADDRESS, path, 0, 0, 0)
        fault, c = abi.red2_control_push(self.control_stack, self.c, entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self.c = c
        return True

    def _peek_control_path(self) -> int | None:
        if type(self.c) is not int or self.c < -1 or self.c >= len(self.control_stack):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        if self.c < 0:
            self._fault(abi.FAULT_CONTROL_UNDERFLOW)
            return None
        entry = self.control_stack[self.c]
        if entry == 0:
            self._fault(abi.FAULT_CONTROL_UNDERFLOW)
            return None
        if type(entry) is not int or entry < 0 or entry >= (1 << abi.CONTROL_WIDTH):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        if abi.control_tag(entry) != abi.CONTROL_ADDRESS:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return None
        return abi.control_field(entry, 0)

    def _pop_control_path(self) -> int | None:
        path = self._peek_control_path()
        if path is None:
            return None
        fault, c, _ = abi.red2_control_pop(self.control_stack, self.c)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return None
        self.c = c
        return path

    def _push_definition_path(self, path: int) -> bool:
        entry = abi.pack_control_entry(
            abi.CONTROL_SAVED_DEFINITION_PATH, path, 0, 0, 0
        )
        fault, c = abi.red2_control_push(self.control_stack, self.c, entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self.c = c
        return True

    def _discard_completed_definition_paths(self) -> None:
        while (
            self.c >= 0
            and abi.control_tag(self.control_stack[self.c])
            == abi.CONTROL_SAVED_DEFINITION_PATH
        ):
            fault, c, _ = abi.red2_control_pop(self.control_stack, self.c)
            if fault != abi.FAULT_NONE:
                self._fault(fault)
                return
            self.c = c

    def _primitive_countdown(self) -> bool:
        if self.fire <= 0:
            return False
        if self.prim_id == 0:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return True
        lazy_fire = (
            self._prim0_role(self.prim_id) == PRIM0_ROLE_IF
            or self.prim_id == self.if_reconstruct_literal_id
        )
        if self.fire == 1 and lazy_fire:
            self._task4_begin(TASK4_IF, TASK4_IF_FIRE)
            self.microstate = MICRO_TASK4
            return True
        struct_fire = (
            self._struct_selector_tag(self.prim_id) != 0
            or self.prim_id == self.cons_literal_id
        )
        if self.fire == 1 and struct_fire:
            self._task4_begin(TASK4_STRUCT, TASK4_STRUCT_SELECTOR_FIRE)
            self.microstate = MICRO_TASK4
            return True
        self.fire -= 1
        if self.fire == 0:
            self._fire_scalar_primitive()
            return True
        return False

    def _scalar_op(self, literal_id: int) -> int:
        if literal_id >= len(self.scalar_ops):
            return SCALAR_OP_NONE
        return self.scalar_ops[literal_id]

    def _host_op(self, literal_id: int) -> int:
        if literal_id < 0 or literal_id >= len(self.host_ops):
            return abi.HOST_NONE
        return self.host_ops[literal_id]

    def _struct_selector_tag(self, literal_id: int) -> int:
        if literal_id < 0 or literal_id >= len(self.struct_selector_tags):
            return 0
        return self.struct_selector_tags[literal_id]

    def _struct_selector_offset(self, literal_id: int) -> int:
        if literal_id < 0 or literal_id >= len(self.struct_selector_offsets):
            return 0
        return self.struct_selector_offsets[literal_id]

    def _bool_word(self, value: bool) -> int | None:
        literal_id = self.true_literal_id if value else self.false_literal_id
        if literal_id <= 0:
            self._fault(abi.FAULT_UNSUPPORTED_VALUE)
            return None
        return self._make_word(abi.MOP_SYM, abi.DATA_LITERAL_ID, literal_id, 1)

    def _is_symbol_value(self, word: int) -> bool:
        return self._opcode(word) in (
            abi.MOP_SYM,
            abi.MOP_PRIM_0,
            abi.MOP_PRIM_1,
            abi.MOP_PRIM_2,
        ) and self._data_kind(word) == abi.DATA_LITERAL_ID

    def _checked_int_result(self, value: int) -> int | None:
        if value < abi.SIGNED_DATA_MIN or value > abi.SIGNED_DATA_MAX:
            self._fault(abi.FAULT_UNSUPPORTED_VALUE)
            return None
        return self._make_word(
            abi.MOP_INT, abi.DATA_SIGNED, abi.signed_to_payload(value), 1
        )

    def _finish_scalar_result(self, result: int | None) -> None:
        self.prim_id = 0
        self.fire = 0
        if self.fault != abi.FAULT_NONE:
            return
        if result is not None:
            self.memory[self.pc] = result
            self.fsp = self.pc
            self.q -= 1
        self.pc -= 1

    def _evaluate_scalar_primitive(
        self,
        op: int,
        memory: list[int],
        pc: int,
    ) -> int | None:
        right = memory[pc]
        if right == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        right_opcode = self._opcode(right)
        right_int = self._signed_data(right)
        result: int | None = None

        if op in (
            SCALAR_OP_DEC,
            SCALAR_OP_INC,
            SCALAR_OP_NEGATE,
            SCALAR_OP_ABS,
            SCALAR_OP_FLOOR,
            SCALAR_OP_CEILING,
            SCALAR_OP_EVEN,
        ):
            if right_opcode == abi.MOP_FLOAT:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            if right_opcode == abi.MOP_INT and right_int is not None:
                if op == SCALAR_OP_DEC:
                    result = self._checked_int_result(right_int - 1)
                elif op == SCALAR_OP_INC:
                    result = self._checked_int_result(right_int + 1)
                elif op == SCALAR_OP_NEGATE:
                    result = self._checked_int_result(-right_int)
                elif op == SCALAR_OP_ABS:
                    result = self._checked_int_result(abs(right_int))
                elif op in (SCALAR_OP_FLOOR, SCALAR_OP_CEILING):
                    result = self._checked_int_result(right_int)
                else:
                    result = self._bool_word(right_int % 2 == 0)
            return result

        if op == SCALAR_OP_NULL:
            if self._is_symbol_value(right):
                result = self._bool_word(self._payload(right) == self.nil_literal_id)
            elif right_opcode not in (abi.MOP_APP, abi.MOP_APP_VAR, abi.MOP_VAR):
                result = self._bool_word(False)
            return result

        if op == SCALAR_OP_NOT:
            if self._is_symbol_value(right):
                if self._payload(right) == self.true_literal_id:
                    result = self._bool_word(False)
                elif self._payload(right) == self.false_literal_id:
                    result = self._bool_word(True)
            return result

        if op in (
            SCALAR_OP_INTEGER_P,
            SCALAR_OP_FLOAT_P,
            SCALAR_OP_CHAR_P,
            SCALAR_OP_SYMBOL_P,
        ):
            if right_opcode not in (abi.MOP_APP, abi.MOP_APP_VAR, abi.MOP_VAR):
                expected = abi.MOP_INT
                if op == SCALAR_OP_FLOAT_P:
                    expected = abi.MOP_FLOAT
                elif op == SCALAR_OP_CHAR_P:
                    expected = abi.MOP_CHAR
                result = self._bool_word(
                    self._is_symbol_value(right)
                    if op == SCALAR_OP_SYMBOL_P
                    else right_opcode == expected
                )
            return result

        left_address = pc + 1
        if not 0 <= left_address < len(memory) or memory[left_address] == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        left = memory[left_address]
        left_opcode = self._opcode(left)
        left_int = self._signed_data(left)

        if op == SCALAR_OP_EQ:
            if left_opcode == abi.MOP_FLOAT or right_opcode == abi.MOP_FLOAT:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            if left_opcode == abi.MOP_INT and right_opcode == abi.MOP_INT:
                result = self._bool_word(left_int == right_int)
            elif left_opcode == abi.MOP_CHAR and right_opcode == abi.MOP_CHAR:
                result = self._bool_word(self._payload(left) == self._payload(right))
            elif self._is_symbol_value(left) and self._is_symbol_value(right):
                result = self._bool_word(self._payload(left) == self._payload(right))
            elif (
                left_opcode not in (abi.MOP_APP, abi.MOP_APP_VAR, abi.MOP_VAR)
                and right_opcode not in (abi.MOP_APP, abi.MOP_APP_VAR, abi.MOP_VAR)
            ):
                result = self._bool_word(False)
            return result

        if left_opcode == abi.MOP_FLOAT or right_opcode == abi.MOP_FLOAT:
            self._fault(abi.FAULT_UNSUPPORTED_VALUE)
            return None
        if left_opcode != abi.MOP_INT or right_opcode != abi.MOP_INT:
            return None
        assert left_int is not None and right_int is not None

        if op == SCALAR_OP_ADD:
            result = self._checked_int_result(left_int + right_int)
        elif op == SCALAR_OP_SUB:
            result = self._checked_int_result(left_int - right_int)
        elif op == SCALAR_OP_MUL:
            result = self._checked_int_result(left_int * right_int)
        elif op == SCALAR_OP_DIV:
            if right_int == 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            if left_int % right_int != 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            result = self._checked_int_result(left_int // right_int)
        elif op == SCALAR_OP_LT:
            result = self._bool_word(left_int < right_int)
        elif op == SCALAR_OP_GT:
            result = self._bool_word(left_int > right_int)
        elif op == SCALAR_OP_LE:
            result = self._bool_word(left_int <= right_int)
        elif op == SCALAR_OP_GE:
            result = self._bool_word(left_int >= right_int)
        elif op == SCALAR_OP_MAX:
            result = self._checked_int_result(max(left_int, right_int))
        elif op == SCALAR_OP_MIN:
            result = self._checked_int_result(min(left_int, right_int))
        elif op == SCALAR_OP_MOD:
            if right_int == 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            result = self._checked_int_result(left_int % right_int)
        elif op == SCALAR_OP_EXPT:
            if right_int < 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            # Every non-trivial power above this exponent is outside signed
            # 64-bit RED2 range. Reject it before Python can construct an
            # arbitrarily large intermediate integer.
            if abs(left_int) >= 2 and right_int > 63:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return None
            result = self._checked_int_result(pow(left_int, right_int))
        else:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return None
        return result

    def _fire_scalar_primitive(self) -> None:
        io_role = self._prim0_role(self.prim_id)
        if io_role in (
            PRIM0_ROLE_IO_BIND,
            PRIM0_ROLE_IO_THEN,
            PRIM0_ROLE_IO_RETURN,
        ):
            self._task4_begin(TASK4_IO, TASK4_IO_FIRE)
            self.microstate = MICRO_TASK4
            return
        host_op = self._host_op(self.prim_id)
        if host_op in (abi.HOST_UART_TX, abi.HOST_UART_TX_BYTES):
            self.prim_id = 0
            self.fire = 0
            if self.q <= 0:
                self.pc -= 1
                return
            self.pending_host_op = host_op
            self.pending_host_argument = abi.encode_optional_address(self.pc)
            return
        if self.prim_id == self.equality_literal_id and self.equality_literal_id > 0:
            self._task4_begin(TASK4_EQUALITY, TASK4_EQUALITY_FIRE)
            self.microstate = MICRO_TASK4
            return
        if self.prim_id == self.equal_if_literal_id and self.equal_if_literal_id > 0:
            self._task4_begin(TASK4_EQUALITY, TASK4_EQUALITY_IF_FIRE)
            self.microstate = MICRO_TASK4
            return
        op = self._scalar_op(self.prim_id)
        if op == SCALAR_OP_NONE:
            # Later slices own host effects; structural equality is routed above.
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if self.q <= 0:
            self._finish_scalar_result(None)
            return
        result = self._evaluate_scalar_primitive(op, self.memory, self.pc)
        if self.fault != abi.FAULT_NONE:
            return
        self._finish_scalar_result(result)

    def _task4_fire_scalar_primitive(self) -> bool:
        primitive_id = self._task_prim_id
        self._task_prim_id = 0
        self._task_fire = 0
        if self._task_q <= 0:
            self._task_pc -= 1
            return True
        op = self._scalar_op(primitive_id)
        if op == SCALAR_OP_NONE:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return False
        result = self._evaluate_scalar_primitive(op, self._task_memory, self._task_pc)
        if self.fault != abi.FAULT_NONE:
            return False
        if result is not None:
            self._task_memory[self._task_pc] = result
            self._task_fsp = self._task_pc
            self._task_q -= 1
        self._task_pc -= 1
        return True

    def _task4_fire_primitive(self) -> bool:
        primitive_id = self._task_prim_id
        if primitive_id == 0:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return False
        host_op = self._host_op(primitive_id)
        if host_op in (abi.HOST_UART_TX, abi.HOST_UART_TX_BYTES):
            self._task_prim_id = 0
            self._task_fire = 0
            if self._task_q <= 0:
                self._task_pc -= 1
                return True
            self._task_pending_host_op = host_op
            self._task_pending_host_argument = abi.encode_optional_address(self._task_pc)
            return True
        if primitive_id == self.if_reconstruct_literal_id:
            self._task_prim_id = 0
            self._task_fire = 0
            restored = self._task4_pop_saved_quantum()
            if restored is None:
                return False
            self._task_q = restored
            self._task_pc -= 1
            return True
        io_role = self._prim0_role(primitive_id)
        if io_role in (
            PRIM0_ROLE_IO_BIND,
            PRIM0_ROLE_IO_THEN,
            PRIM0_ROLE_IO_RETURN,
        ):
            self._task4_kind = TASK4_IO
            self._task4_phase = TASK4_IO_FIRE
            return False
        if io_role == PRIM0_ROLE_IF:
            self._task4_kind = TASK4_IF
            self._task4_phase = TASK4_IF_FIRE
            return False
        if primitive_id == self.struct_selector_result_literal_id:
            self._task4_kind = TASK4_STRUCT
            self._task4_phase = TASK4_STRUCT_SELECTOR_RESULT
            return False
        if self._struct_selector_tag(primitive_id) != 0 or primitive_id == self.cons_literal_id:
            self._task4_kind = TASK4_STRUCT
            self._task4_phase = TASK4_STRUCT_SELECTOR_FIRE
            return False
        if primitive_id == self.equality_literal_id and self.equality_literal_id > 0:
            self._task4_kind = TASK4_EQUALITY
            self._task4_phase = TASK4_EQUALITY_FIRE
            return False
        if primitive_id == self.equality_continue_literal_id and self.equality_continue_literal_id > 0:
            self._task4_kind = TASK4_EQUALITY
            self._task4_phase = TASK4_EQUALITY_CONTINUE
            return False
        if primitive_id == self.equal_if_literal_id and self.equal_if_literal_id > 0:
            self._task4_kind = TASK4_EQUALITY
            self._task4_phase = TASK4_EQUALITY_IF_FIRE
            return False
        return self._task4_fire_scalar_primitive()

    def _task4_if_clock(self) -> None:
        if self._task4_phase == TASK4_IF_FIRE:
            if self._task_fire > 1:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_fire == 1:
                self._task_fire = 0
            primitive_id = self._task_prim_id
            if primitive_id == 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if primitive_id == self.if_reconstruct_literal_id:
                self._task_prim_id = 0
                restored = self._task4_pop_saved_quantum()
                if restored is None:
                    return
                self._task_q = restored
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            if self._prim0_role(primitive_id) != PRIM0_ROLE_IF:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            false_slot = self._task_pc - 2
            true_slot = self._task_pc - 1
            if false_slot < 0 or true_slot < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            false_branch = self._task_memory[false_slot]
            true_branch = self._task_memory[true_slot]
            condition = self._task_memory[self._task_pc]
            if false_branch == 0 or true_branch == 0 or condition == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return

            true_path = None
            true_opcode = self._opcode(true_branch)
            if true_opcode == abi.MOP_APP or true_opcode == abi.MOP_EP:
                true_path = self._task4_pop_control_path()
                if true_path is None:
                    return
            false_path = None
            false_opcode = self._opcode(false_branch)
            if false_opcode == abi.MOP_APP or false_opcode == abi.MOP_EP:
                false_path = self._task4_pop_control_path()
                if false_path is None:
                    return

            self._task_prim_id = 0
            condition_is_boolean = (
                self._opcode(condition) == abi.MOP_SYM
                and self._data_kind(condition) == abi.DATA_LITERAL_ID
                and self._payload(condition) in (
                    self.true_literal_id,
                    self.false_literal_id,
                )
            )
            if condition_is_boolean:
                if self._task_q == 0:
                    self._task_pc = false_slot - 1
                    self.microstate = MICRO_COMMIT
                    return
                selected_true = self._payload(condition) == self.true_literal_id
                selected = true_branch if selected_true else false_branch
                selected_path = true_path if selected_true else false_path
                selected_opcode = self._opcode(selected)
                self._task_q -= 1
                if selected_opcode == abi.MOP_APP:
                    target = self._signed_data(selected)
                    if target is None or target < 0 or selected_path is None:
                        self._fault(
                            abi.FAULT_INVALID_ADDRESS
                            if target is None or target < 0
                            else abi.FAULT_ILLEGAL_TRANSITION
                        )
                        return
                    self._task_fsp = false_slot - 1
                    self._task_env = selected_path
                    self._task_pc = target
                    self._task_direction = abi.DIRECTION_FORWARD
                    self.microstate = MICRO_COMMIT
                    return
                if selected_opcode == abi.MOP_EP:
                    target = self._signed_data(selected)
                    if target is None or target < 0 or selected_path is None:
                        self._fault(
                            abi.FAULT_INVALID_ADDRESS
                            if target is None or target < 0
                            else abi.FAULT_ILLEGAL_TRANSITION
                        )
                        return
                    self._task_env = selected_path
                    self._task_if_target = target
                    self._task_if_hops = 0
                    self._task_if_false_slot = false_slot
                    self._task4_phase = TASK4_IF_EP_CHASE
                    return
                self._task_memory[false_slot] = self._make_word(
                    selected_opcode,
                    self._data_kind(selected),
                    self._payload(selected),
                    1,
                    self._definition_valid(selected),
                    self._definition(selected),
                )
                self._task_fsp = false_slot
                self._task_pc = false_slot
                self.microstate = MICRO_COMMIT
                return

            if self.if_reconstruct_literal_id <= 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            saved_q = self._task_q
            if not self._task4_push_saved_quantum(saved_q):
                return
            if false_path is not None and not self._task4_push_control_path(false_path):
                return
            if true_path is not None and not self._task4_push_control_path(true_path):
                return
            self._task_q = 0
            self._task_prim_id = self.if_reconstruct_literal_id
            self._task_fire = int(false_path is not None) + int(true_path is not None)
            self._task_pc -= 1
            if self._task_fire == 0:
                restored = self._task4_pop_saved_quantum()
                if restored is None:
                    return
                self._task_q = restored
                self._task_prim_id = 0
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase == TASK4_IF_EP_CHASE:
            target_address = self._task_if_target
            if target_address < 0 or target_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            target = self._task_memory[target_address]
            if target == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(target) == abi.MOP_EP:
                next_address = self._signed_data(target)
                if next_address is None or next_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_if_hops += 1
                if self._task_if_hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_if_target = next_address
                return
            false_slot = self._task_if_false_slot
            if self._is_shareable_atomic(target):
                self._task_memory[false_slot] = self._make_word(
                    self._opcode(target),
                    self._data_kind(target),
                    self._payload(target),
                    1,
                    self._definition_valid(target),
                    self._definition(target),
                )
                self._task_fsp = false_slot
                self._task_pc = false_slot
                self._task_direction = abi.DIRECTION_REVERSE
                self.microstate = MICRO_COMMIT
                return
            if self._opcode(target) == abi.MOP_CLOSURE:
                self._task_fsp = false_slot - 1
                self._task_pc = target_address
                self._task_direction = abi.DIRECTION_FORWARD
                self.microstate = MICRO_COMMIT
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _prim0_role(self, literal_id: int) -> int:
        if literal_id >= len(self.prim0_roles):
            return PRIM0_ROLE_PASSIVE
        return self.prim0_roles[literal_id]

    def _push_subgraph_frame(self, env: int, free_space: int) -> bool:
        entry = abi.pack_control_entry(
            abi.CONTROL_SUBGRAPH,
            env,
            free_space,
            self.prim_id,
            self.fire,
        )
        fault, c = abi.red2_control_push(self.control_stack, self.c, entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self.c = c
        return True

    def _pop_subgraph_frame(self) -> tuple[int, int, int, int] | None:
        if self.c < 0:
            return None
        entry = self.control_stack[self.c]
        if abi.control_tag(entry) != abi.CONTROL_SUBGRAPH:
            return None
        fault, c, entry = abi.red2_control_pop(self.control_stack, self.c)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return None
        self.c = c
        return (
            abi.control_field(entry, 0),
            abi.control_field(entry, 1),
            abi.control_field(entry, 2),
            abi.control_field(entry, 3),
        )

    def _push_environment_marker(self, parent: int) -> bool:
        fault, env, free_space = abi.red2_push_environment_marker(
            self.memory, self.fsp, self.free_space, parent
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self.env = env
        self.free_space = free_space
        return True

    def _subgraph_entry_fault(self, parent_env: int, control_c: int) -> int:
        layout_fault = abi._memory_layout_fault(
            self.memory, self.fsp, self.free_space
        )
        if layout_fault != abi.FAULT_NONE:
            return layout_fault
        if not 0 <= parent_env <= len(self.memory):
            return abi.FAULT_INVALID_ADDRESS
        frontier = self.free_space
        normalized_env = parent_env if parent_env == frontier else frontier - 1
        join_address = self.fsp + 1
        if normalized_env <= self.fsp or join_address >= normalized_env:
            return abi.FAULT_GRAPH_ENV_COLLISION
        if type(control_c) is not int or control_c < -1 or control_c >= len(self.control_stack):
            return abi.FAULT_INVALID_ADDRESS
        if control_c + 1 >= len(self.control_stack):
            return abi.FAULT_CONTROL_OVERFLOW
        return abi.FAULT_NONE

    def _enter_subgraph(self, parent_env: int, child_pc: int, parent_pc: int) -> None:
        fault = self._subgraph_entry_fault(parent_env, self.c)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return
        frontier = self.free_space
        normalized_env = parent_env
        needs_bridge = parent_env != frontier
        if needs_bridge:
            normalized_env = frontier - 1
        if needs_bridge:
            marker = self._make_word(
                abi.MOP_PNP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(parent_env),
                0,
            )
            self.memory[normalized_env] = marker
            self.free_space = normalized_env
        self.env = normalized_env
        if not self._push_subgraph_frame(normalized_env, normalized_env):
            return
        saved_fire = self.fire
        self.prim_id = 0
        self.fire = 0
        join = self._make_word(
            abi.MOP_JOIN,
            abi.DATA_SIGNED,
            abi.signed_to_payload(parent_pc),
            0,
            int(saved_fire > 0),
            1 if saved_fire > 0 else 0,
        )
        fault, fsp, _ = abi.red2_push_graph(
            self.memory, self.fsp, self.free_space, join
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return
        self.fsp = fsp
        self.argcnt = 0
        self.pc = child_pc
        self.direction = abi.DIRECTION_FORWARD

    def _allocate_environment(self, word: int) -> bool:
        fault, _, env, free_space = abi.red2_allocate_environment(
            self.memory, self.fsp, self.env, self.free_space, word
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self.env = env
        self.free_space = free_space
        return True

    def _is_shareable_atomic(self, word: int) -> bool:
        opcode = self._opcode(word)
        if opcode in (abi.MOP_INT, abi.MOP_FLOAT, abi.MOP_CHAR):
            return True
        return opcode == abi.MOP_SYM and not self._definition_valid(word)

    def _execute(self, word: int) -> None:
        opcode = self._opcode(word)
        if opcode == abi.MOP_APP:
            self._execute_app(word)
        elif opcode == abi.MOP_APP_VAR:
            self._execute_app_var(word)
        elif opcode == abi.MOP_LAMBDA:
            self._execute_lambda(word)
        elif opcode == abi.MOP_CLOSURE:
            self._execute_closure(word)
        elif opcode == abi.MOP_EP:
            self._execute_ep(word)
        elif opcode == abi.MOP_JOIN:
            self._execute_join(word)
        elif opcode == abi.MOP_SYM:
            self._execute_sym(word)
        elif opcode in (abi.MOP_PRIM_0, abi.MOP_PRIM_1, abi.MOP_PRIM_2):
            self._execute_prim(word)
        elif opcode == abi.MOP_STOP:
            self._execute_stop()
        elif opcode in (abi.MOP_INT, abi.MOP_FLOAT, abi.MOP_CHAR):
            self._execute_passive(word)
        elif opcode == abi.MOP_UBV:
            self._execute_ubv(word)
        elif opcode == abi.MOP_VAR:
            self._execute_var(word)
        elif opcode == abi.MOP_RBLOCK:
            self._execute_rblock(word)
        elif opcode == abi.MOP_RUP:
            self._execute_rup(word)
        elif opcode == abi.MOP_RECP:
            self._execute_recp(word)
        elif opcode == abi.MOP_STRUCT:
            self._execute_struct(word)
        else:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _execute_passive(self, word: int) -> None:
        opcode = self._opcode(word)
        kind = self._data_kind(word)
        if opcode == abi.MOP_INT and kind != abi.DATA_SIGNED:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if opcode == abi.MOP_FLOAT and kind != abi.DATA_FLOAT64:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if opcode == abi.MOP_CHAR and kind != abi.DATA_LITERAL_ID:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if self.direction == abi.DIRECTION_REVERSE:
            if self._primitive_countdown():
                return
            self.pc -= 1
            return
        if not self._push_result(word):
            return
        if self._head(word):
            self.pc = self.fsp - 1
            self.direction = abi.DIRECTION_REVERSE
        else:
            self.pc += 1

    def _execute_sym(self, word: int) -> None:
        if self._data_kind(word) != abi.DATA_LITERAL_ID or self._payload(word) == 0:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if self.direction == abi.DIRECTION_REVERSE:
            if self._head(word) and self._definition_valid(word) and self.q > 0:
                next_path = self.pc - 1
                if next_path < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if not self._push_definition_path(self.env):
                    return
                self.memory[self.pc] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(next_path),
                    self._head(word),
                    1,
                    self._definition(word),
                )
                self.argcnt -= 1
                return
            if self._primitive_countdown():
                return
            self.pc -= 1
            return
        if not self._push_result(word):
            return
        if self._head(word):
            self.pc = (
                self.fsp
                if self._definition_valid(word) and self.q > 0
                else self.fsp - 1
            )
            self.direction = abi.DIRECTION_REVERSE
        else:
            self.pc += 1

    def _execute_prim(self, word: int) -> None:
        if self._data_kind(word) != abi.DATA_LITERAL_ID or self._payload(word) == 0:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if self.direction == abi.DIRECTION_REVERSE:
            self.pc -= 1
            return
        opcode = self._opcode(word)
        literal_id = self._payload(word)
        arity = 0
        if opcode == abi.MOP_PRIM_1:
            arity = 1
        elif opcode == abi.MOP_PRIM_2:
            arity = 2
        elif opcode == abi.MOP_PRIM_0:
            if (
                self._head(word)
                and literal_id == self.equal_star_literal_id
                and self.equal_star_literal_id > 0
            ):
                self._task4_begin(TASK4_EQUALITY, TASK4_EQUALITY_CHILD_INIT)
                self.microstate = MICRO_TASK4
                return
            if (
                self._head(word)
                and literal_id == self.equal_if_literal_id
                and self.equal_if_literal_id > 0
                and self.argcnt >= 3
            ):
                self.prim_id = literal_id
                self.fire = 1
            role = self._prim0_role(literal_id)
            if self._head(word) and role == PRIM0_ROLE_Y:
                self._execute_y(word)
                return
            host_op = self._host_op(literal_id)
            if (
                self._head(word)
                and host_op in (abi.HOST_CLOCK, abi.HOST_UART_RX)
                and self.argcnt == 0
                and self.q > 0
            ):
                self.pending_host_op = host_op
                self.pending_host_argument = 0
                return
            if (
                self._head(word)
                and role == PRIM0_ROLE_IF
                and self.argcnt >= 3
                and self.q > 0
            ):
                self.prim_id = literal_id
                self.fire = 1
            elif (
                self._head(word)
                and role in (PRIM0_ROLE_IO_BIND, PRIM0_ROLE_IO_THEN)
                and self.argcnt >= 2
                and self.q > 0
            ):
                self.prim_id = literal_id
                self.fire = 1
            elif self._head(word) and role == PRIM0_ROLE_DEFERRED and self.q > 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
        else:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if arity > 0 and self._head(word) and self.argcnt >= arity and self.q > 0:
            self.prim_id = literal_id
            self.fire = arity
        if not self._push_result(word):
            return
        if self._head(word):
            self.pc = self.fsp - 1
            self.direction = abi.DIRECTION_REVERSE
        else:
            self.pc += 1

    def _execute_y(self, word: int) -> None:
        if self.q == 0 or self.argcnt < 1:
            if not self._push_result(word):
                return
            self.pc = self.fsp - 1
            self.direction = abi.DIRECTION_REVERSE
            return
        argument_address = self.pc - 1
        if argument_address < 0 or argument_address >= len(self.memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        argument = self.memory[argument_address]
        if argument == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        if self.fsp < 0 or self.fsp >= len(self.memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        recursive = self._make_word(
            abi.MOP_APP,
            abi.DATA_SIGNED,
            abi.signed_to_payload(argument_address),
            0,
        )
        if self._opcode(argument) == abi.MOP_APP:
            target = self._signed_data(argument)
            if target is None or target < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self.q -= 1
            self.memory[self.fsp] = recursive
            self.pc = target
            return

        scratch = self.fsp + 1
        if scratch >= self.free_space or scratch >= len(self.memory):
            self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
            return
        if not 0 <= self.env <= len(self.memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        if type(self.c) is not int or self.c < -1 or self.c >= len(self.control_stack):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        if self.c + 1 >= len(self.control_stack):
            self._fault(abi.FAULT_CONTROL_OVERFLOW)
            return
        path_entry = abi.pack_control_entry(
            abi.CONTROL_ADDRESS, self.env, 0, 0, 0
        )
        fault, c = abi.red2_control_push(self.control_stack, self.c, path_entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return
        self.c = c
        self.q -= 1
        self.memory[self.fsp] = recursive
        self.memory[scratch] = self._make_word(
            self._opcode(argument),
            self._data_kind(argument),
            self._payload(argument),
            1,
            self._definition_valid(argument),
            self._definition(argument),
        )
        self.pc = scratch

    def _execute_app(self, word: int) -> None:
        if self.direction == abi.DIRECTION_FORWARD:
            if not 0 <= self.env <= len(self.memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if type(self.c) is not int or self.c < -1 or self.c >= len(self.control_stack):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self.c + 1 >= len(self.control_stack):
                self._fault(abi.FAULT_CONTROL_OVERFLOW)
                return
            if not self._push_result(word):
                return
            if not self._push_control_path(self.env):
                return
            self.pc += 1
            return
        if self._definition_valid(word) and self.q > 0:
            if (
                self.c >= 0
                and abi.control_tag(self.control_stack[self.c])
                == abi.CONTROL_SAVED_DEFINITION_PATH
            ):
                fault, c, _ = abi.red2_control_pop(self.control_stack, self.c)
                if fault != abi.FAULT_NONE:
                    self._fault(fault)
                    return
                self.c = c
            self.memory[self.pc] = self._make_word(abi.MOP_STOP, abi.DATA_NONE, 0, 0)
            self.fsp -= 1
            self.pc = self._definition(word)
            self.direction = abi.DIRECTION_FORWARD
            self.q -= 1
            return
        child_pc = self._signed_data(word)
        if child_pc is None or child_pc < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        parent_app = self.pc
        parent_env = self._peek_control_path()
        if parent_env is None:
            return
        fault = self._subgraph_entry_fault(parent_env, self.c - 1)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return
        popped_parent_env = self._pop_control_path()
        if popped_parent_env is None:
            return
        self._enter_subgraph(popped_parent_env, child_pc, parent_app)

    def _execute_app_var(self, word: int) -> None:
        if self.direction == abi.DIRECTION_REVERSE:
            self.pc -= 1
            return
        index = self._signed_data(word)
        if index is None or index < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        self._task4_begin(TASK4_APP_VAR, TASK4_APP_VAR_LOOKUP)
        self._task_var_address = self._task_env
        self._task_var_remaining = index
        self._task_var_hops = 0
        self._task_s_d = index
        self._task_s_d_valid = 1
        self.microstate = MICRO_TASK4
    def _execute_closure(self, word: int) -> None:
        if self.direction != abi.DIRECTION_FORWARD:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        captured_env = self._signed_data(word)
        if captured_env is None or captured_env < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        code_address = self.pc + 1
        if not 0 <= code_address < len(self.memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        code = self.memory[code_address]
        if code == 0 or self._opcode(code) != abi.MOP_NONE:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        target = self._signed_data(code)
        if target is None or target < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        if not self._push_environment_marker(captured_env):
            return
        self.pc = target

    def _execute_ep(self, word: int) -> None:
        target_address = self._signed_data(word)
        if target_address is None or target_address < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        self._task4_begin(TASK4_EP, TASK4_EP_CHASE)
        self._task_ep_target = target_address
        self._task_ep_hops = 0
        self._task_ep_parent = self._task_pc
        self.microstate = MICRO_TASK4
    def _validate_subgraph_return(self, frame_env: int, frame_free_space: int) -> bool:
        current_frontier = self.free_space
        if not 0 <= current_frontier <= frame_free_space <= len(self.memory):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return False
        if not 0 <= frame_env <= len(self.memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        if current_frontier <= frame_env < frame_free_space:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return False
        return True

    def _restore_subgraph_region(self, frame_env: int, frame_free_space: int) -> bool:
        if not self._validate_subgraph_return(frame_env, frame_free_space):
            return False
        self.free_space = frame_free_space
        self.env = frame_env
        return True

    def _task4_begin(self, kind: int, next_phase: int) -> None:
        self._task_pc = self.pc
        self._task_fsp = self.fsp
        self._task_env = self.env
        self._task_c = self.c
        self._task_direction = self.direction
        self._task_q = self.q
        self._task_phi = self.phi
        self._task_free_space = self.free_space
        self._task_argcnt = self.argcnt
        self._task_prim_id = self.prim_id
        self._task_fire = self.fire
        self._task_s_a = 0 if self.s_a is None else self.s_a
        self._task_s_a_valid = int(self.s_a is not None)
        self._task_s_d = 0 if self.s_d is None else self.s_d
        self._task_s_d_valid = int(self.s_d is not None)
        self._task_halted = self.halted
        self._task_pending_host_op = self.pending_host_op
        self._task_pending_host_argument = self.pending_host_argument
        self._task_sp = -1
        self._task_mat_count = 0
        self._task_mat_visit_count = 0
        self._task4_active = 1
        self._task4_kind = kind
        self._task4_phase = TASK4_COPY_MEMORY
        self._task_next_phase = next_phase
        self._task_copy_index = 0
        self._task_pub_value = 0

    def _task4_commit(self) -> None:
        # Architectural RAM/control arrays model persistent hardware storage.  The
        # Task-4 shadow buffers provide failure atomicity, but publishing a commit
        # must not replace those architectural storage objects.  Copy the fully
        # validated shadow contents in place at the commit boundary; the next
        # Task-4 transaction refreshes its shadows from live state before use.
        for index in range(len(self.memory)):
            self.memory[index] = self._task_memory[index]
        for index in range(len(self.control_stack)):
            self.control_stack[index] = self._task_control[index]
        self.pc = self._task_pc
        self.fsp = self._task_fsp
        self.env = self._task_env
        self.c = self._task_c
        self.direction = self._task_direction
        self.q = self._task_q
        self.phi = self._task_phi
        self.free_space = self._task_free_space
        self.argcnt = self._task_argcnt
        self.prim_id = self._task_prim_id
        self.fire = self._task_fire
        self.s_a = self._task_s_a if self._task_s_a_valid else -1
        self.s_d = self._task_s_d if self._task_s_d_valid else -1
        self.halted = self._task_halted
        self.pending_host_op = self._task_pending_host_op
        self.pending_host_argument = self._task_pending_host_argument
        self._task4_active = 0
        self._task4_kind = TASK4_NONE
        self._task4_phase = 0
        self._task_sp = -1

    def _task4_push(
        self,
        kind: int,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        d: int = 0,
        e: int = 0,
        f: int = 0,
        g: int = 0,
        h: int = 0,
    ) -> bool:
        next_sp = self._task_sp + 1
        if next_sp >= len(self._task_stack_kind):
            self._fault(abi.FAULT_CONTROL_OVERFLOW)
            return False
        self._task_sp = next_sp
        self._task_stack_kind[next_sp] = kind
        self._task_stack_a[next_sp] = a
        self._task_stack_b[next_sp] = b
        self._task_stack_c[next_sp] = c
        self._task_stack_d[next_sp] = d
        self._task_stack_e[next_sp] = e
        self._task_stack_f[next_sp] = f
        self._task_stack_g[next_sp] = g
        self._task_stack_h[next_sp] = h
        return True

    def _task4_is_inline(self, word: int) -> bool:
        opcode = self._opcode(word)
        return (
            opcode == abi.MOP_INT
            or opcode == abi.MOP_FLOAT
            or opcode == abi.MOP_CHAR
            or opcode == abi.MOP_SYM
            or opcode == abi.MOP_PRIM_0
            or opcode == abi.MOP_PRIM_1
            or opcode == abi.MOP_PRIM_2
        )

    def _task4_is_app_prefix(self, word: int) -> bool:
        opcode = self._opcode(word)
        return (
            opcode == abi.MOP_APP
            or opcode == abi.MOP_APP_VAR
            or (not self._head(word) and self._task4_is_inline(word))
        )

    def _task4_mat_append(self, word: int) -> bool:
        if self._task_mat_count >= len(self._task_mat_words):
            self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
            return False
        slot = self._task_mat_count
        self._task_mat_words[slot] = word
        self._task_mat_valid[slot] = 1
        self._task_mat_count += 1
        return True

    def _task4_task_push_result(self, word: int) -> bool:
        destination = self._task_fsp + 1
        if destination < 0 or destination >= len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        if destination >= self._task_free_space:
            self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
            return False
        self._task_memory[destination] = word
        self._task_fsp = destination
        self._task_argcnt += 1
        return True

    def _task4_push_control_path(self, path: int) -> bool:
        entry = abi.pack_control_entry(abi.CONTROL_ADDRESS, path, 0, 0, 0)
        fault, c = abi.red2_control_push(self._task_control, self._task_c, entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_c = c
        return True

    def _task4_pop_control_path(self) -> int | None:
        if (
            type(self._task_c) is not int
            or self._task_c < -1
            or self._task_c >= len(self._task_control)
        ):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        if self._task_c < 0:
            self._fault(abi.FAULT_CONTROL_UNDERFLOW)
            return None
        entry = self._task_control[self._task_c]
        if entry == 0:
            self._fault(abi.FAULT_CONTROL_UNDERFLOW)
            return None
        if type(entry) is not int or entry < 0 or entry >= (1 << abi.CONTROL_WIDTH):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        if abi.control_tag(entry) != abi.CONTROL_ADDRESS:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return None
        path = abi.control_field(entry, 0)
        fault, c, _ = abi.red2_control_pop(self._task_control, self._task_c)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return None
        self._task_c = c
        return path

    def _task4_push_saved_quantum(self, quantum: int) -> bool:
        entry = abi.pack_control_entry(
            abi.CONTROL_SAVED_QUANTUM, quantum, 0, 0, 0
        )
        fault, c = abi.red2_control_push(self._task_control, self._task_c, entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_c = c
        return True

    def _task4_pop_saved_quantum(self) -> int | None:
        if self._task_c < 0 or self._task_c >= len(self._task_control):
            self._fault(abi.FAULT_CONTROL_UNDERFLOW)
            return None
        entry = self._task_control[self._task_c]
        if (
            type(entry) is not int
            or entry < 0
            or entry >= (1 << abi.CONTROL_WIDTH)
        ):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return None
        if abi.control_tag(entry) != abi.CONTROL_SAVED_QUANTUM:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return None
        quantum = abi.control_field(entry, 0)
        fault, c, _ = abi.red2_control_pop(self._task_control, self._task_c)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return None
        self._task_c = c
        return quantum

    def _task4_push_environment_marker(self, parent: int) -> bool:
        fault, env, free_space = abi.red2_push_environment_marker(
            self._task_memory,
            self._task_fsp,
            self._task_free_space,
            parent,
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_env = env
        self._task_free_space = free_space
        return True

    def _task4_enter_subgraph(self, parent_env: int, child_pc: int, parent_pc: int) -> bool:
        layout_fault = abi._memory_layout_fault(
            self._task_memory, self._task_fsp, self._task_free_space
        )
        if layout_fault != abi.FAULT_NONE:
            self._fault(layout_fault)
            return False
        if not 0 <= parent_env <= len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        frontier = self._task_free_space
        normalized_env = parent_env
        needs_bridge = parent_env != frontier
        if needs_bridge:
            normalized_env = frontier - 1
        join_address = self._task_fsp + 1
        if normalized_env <= self._task_fsp or join_address >= normalized_env:
            self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
            return False
        if (
            type(self._task_c) is not int
            or self._task_c < -1
            or self._task_c >= len(self._task_control)
        ):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        if self._task_c + 1 >= len(self._task_control):
            self._fault(abi.FAULT_CONTROL_OVERFLOW)
            return False
        if needs_bridge:
            self._task_memory[normalized_env] = self._make_word(
                abi.MOP_PNP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(parent_env),
                0,
            )
            self._task_free_space = normalized_env
        self._task_env = normalized_env
        frame = abi.pack_control_entry(
            abi.CONTROL_SUBGRAPH,
            normalized_env,
            normalized_env,
            self._task_prim_id,
            self._task_fire,
        )
        fault, c = abi.red2_control_push(self._task_control, self._task_c, frame)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_c = c
        saved_fire = self._task_fire
        self._task_prim_id = 0
        self._task_fire = 0
        join = self._make_word(
            abi.MOP_JOIN,
            abi.DATA_SIGNED,
            abi.signed_to_payload(parent_pc),
            0,
            int(saved_fire > 0),
            1 if saved_fire > 0 else 0,
        )
        fault, fsp, _ = abi.red2_push_graph(
            self._task_memory,
            self._task_fsp,
            self._task_free_space,
            join,
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_fsp = fsp
        self._task_argcnt = 0
        self._task_pc = child_pc
        self._task_direction = abi.DIRECTION_FORWARD
        return True

    def _task4_start_publication(self, address: int) -> bool:
        self._task_sp = -1
        return self._task4_push(TASK4_PUB_GRAPH, address)

    def _task4_copy_clock(self) -> None:
        if self._task4_phase == TASK4_COPY_MEMORY:
            index = self._task_copy_index
            if index < len(self.memory):
                self._task_memory[index] = self.memory[index]
                self._task_pub_root_state[index] = 0
                self._task_pub_root_result[index] = 0
                self._task_pub_closure_valid[index] = 0
                self._task_pub_closure_result[index] = 0
                self._task_pub_rec_valid[index] = 0
                self._task_pub_rec_result[index] = 0
                self._task_mat_valid[index] = 0
                self._task_copy_index = index + 1
                return
            self._task_copy_index = 0
            self._task4_phase = TASK4_COPY_CONTROL
            return
        if self._task4_phase == TASK4_COPY_CONTROL:
            index = self._task_copy_index
            if index < len(self.control_stack):
                self._task_control[index] = self.control_stack[index]
                self._task_copy_index = index + 1
                return
            self._task_copy_index = 0
            self._task4_phase = self._task_next_phase
            return
        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task4_materialization_clock(self, kind: int) -> None:
        sp = self._task_sp
        if kind == TASK4_MAT_LEAVE:
            expected = self._task_stack_a[sp]
            if self._task_mat_visit_count <= 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_mat_visit_count - 1 != expected:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_mat_visit_count -= 1
            self._task_sp -= 1
            return

        if kind == TASK4_MAT_REHEAD:
            base = self._task_stack_a[sp]
            head = self._task_stack_b[sp]
            if base < 0 or base >= self._task_mat_count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if not self._task_mat_valid[base]:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_mat_words[base] = self._clone_word(
                self._task_mat_words[base], head
            )
            self._task_sp -= 1
            return

        if kind == TASK4_MAT_CLOSURE:
            closure_address = self._task_stack_a[sp]
            requested_head = self._task_stack_b[sp]
            if closure_address < 0 or closure_address + 1 >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            closure = self._task_memory[closure_address]
            code = self._task_memory[closure_address + 1]
            captured_environment = self._signed_data(closure) if closure else None
            code_target = self._signed_data(code) if code else None
            if closure == 0 or self._opcode(closure) != abi.MOP_CLOSURE:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if (
                captured_environment is None
                or captured_environment < 0
                or code == 0
                or self._opcode(code) != abi.MOP_NONE
                or code_target is None
                or code_target < 0
            ):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            base = self._task_mat_count
            self._task_sp -= 1
            if requested_head >= 0:
                if not self._task4_push(TASK4_MAT_REHEAD, base, requested_head):
                    return
            self._task4_push(
                TASK4_MAT_GRAPH,
                code_target,
                captured_environment,
                0,
                1,
            )
            return

        if kind == TASK4_MAT_GRAPH:
            address = self._task_stack_a[sp]
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task_memory[address] == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_stack_kind[sp] = TASK4_MAT_VISIT_SCAN
            self._task_stack_e[sp] = 0
            return

        if kind == TASK4_MAT_VISIT_SCAN:
            address = self._task_stack_a[sp]
            environment = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            head = self._task_stack_d[sp]
            visit_index = self._task_stack_e[sp]
            if visit_index < self._task_mat_visit_count:
                if (
                    self._task_mat_visit_address[visit_index] == address
                    and self._task_mat_visit_environment[visit_index] == environment
                    and self._task_mat_visit_depth[visit_index] == depth
                    and self._task_mat_visit_head[visit_index] == head
                ):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_e[sp] = visit_index + 1
                return
            if self._task_mat_visit_count >= len(self._task_mat_visit_address):
                self._fault(abi.FAULT_CONTROL_OVERFLOW)
                return
            word = self._task_memory[address]
            visit_index = self._task_mat_visit_count
            self._task_mat_visit_address[visit_index] = address
            self._task_mat_visit_environment[visit_index] = environment
            self._task_mat_visit_depth[visit_index] = depth
            self._task_mat_visit_head[visit_index] = head
            self._task_mat_visit_count += 1
            self._task_sp -= 1
            if not self._task4_push(TASK4_MAT_LEAVE, visit_index):
                return
            opcode = self._opcode(word)
            if self._task4_is_app_prefix(word):
                self._task4_push(
                    TASK4_MAT_APP_SCAN,
                    address,
                    environment,
                    depth,
                    head,
                    self._task_mat_count,
                    0,
                )
                return
            if opcode == abi.MOP_LAMBDA:
                self._task4_push(
                    TASK4_MAT_LAMBDA_SCAN,
                    address,
                    environment,
                    depth,
                    head,
                    0,
                )
                return
            if opcode == abi.MOP_STRUCT:
                if not self._task4_mat_append(
                    self._make_word(
                        abi.MOP_STRUCT,
                        self._data_kind(word),
                        self._payload(word),
                        0,
                        self._definition_valid(word),
                        self._definition(word),
                    )
                ):
                    return
                self._task4_push(
                    TASK4_MAT_STRUCT_SCAN,
                    address + 1,
                    environment,
                    depth,
                    head,
                    self._task_mat_count,
                    0,
                )
                return
            if opcode == abi.MOP_VAR:
                index = self._signed_data(word)
                if index is None or index < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if index < depth:
                    self._task4_mat_append(
                        self._make_word(
                            abi.MOP_VAR,
                            abi.DATA_SIGNED,
                            abi.signed_to_payload(index),
                            head,
                            self._definition_valid(word),
                            self._definition(word),
                        )
                    )
                    return
                self._task4_push(
                    TASK4_MAT_LOOKUP,
                    environment,
                    index - depth,
                    head,
                    depth,
                    0,
                    0,
                    address,
                    0,
                )
                return
            if opcode == abi.MOP_EP:
                target = self._signed_data(word)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task4_push(TASK4_MAT_ENV_CHASE, target, head, depth, 0)
                return
            if self._task4_is_inline(word):
                self._task4_mat_append(
                    self._make_word(
                        opcode,
                        self._data_kind(word),
                        self._payload(word),
                        head,
                        self._definition_valid(word),
                        self._definition(word),
                    )
                )
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_MAT_APP_SCAN:
            cursor = self._task_stack_a[sp]
            environment = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            base = self._task_stack_e[sp]
            count = self._task_stack_f[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            entry = self._task_memory[cursor]
            if entry == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task4_is_app_prefix(entry):
                if self._task_mat_count >= len(self._task_mat_words):
                    self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                    return
                self._task_mat_valid[self._task_mat_count] = 0
                self._task_mat_count += 1
                self._task_stack_a[sp] = cursor + 1
                self._task_stack_f[sp] = count + 1
                return
            self._task_sp -= 1
            if not self._task4_push(
                TASK4_MAT_APP_PROCESS,
                cursor - count,
                environment,
                depth,
                base,
                count,
                0,
            ):
                return
            self._task4_push(TASK4_MAT_GRAPH, cursor, environment, depth, 1)
            return

        if kind == TASK4_MAT_APP_PROCESS:
            source_start = self._task_stack_a[sp]
            environment = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            base = self._task_stack_d[sp]
            count = self._task_stack_e[sp]
            index = self._task_stack_f[sp]
            if index >= count:
                self._task_sp -= 1
                return
            source = source_start + index
            slot = base + index
            if source < 0 or source >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if slot < 0 or slot >= len(self._task_mat_words):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            entry = self._task_memory[source]
            opcode = self._opcode(entry)
            if opcode == abi.MOP_APP:
                target = self._signed_data(entry)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_mat_count),
                    0,
                    self._definition_valid(entry),
                    self._definition(entry),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_f[sp] = index + 1
                self._task4_push(TASK4_MAT_GRAPH, target, environment, depth, 1)
                return
            if opcode == abi.MOP_APP_VAR:
                variable = self._signed_data(entry)
                if variable is None or variable < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if variable < depth:
                    self._task_mat_words[slot] = self._make_word(
                        abi.MOP_APP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(variable),
                        0,
                        self._definition_valid(entry),
                        self._definition(entry),
                    )
                    self._task_mat_valid[slot] = 1
                    self._task_stack_f[sp] = index + 1
                    return
                self._task_stack_f[sp] = index + 1
                self._task4_push(
                    TASK4_MAT_LOOKUP,
                    environment,
                    variable - depth,
                    1,
                    depth,
                    1,
                    slot,
                    source,
                    0,
                )
                return
            if not self._head(entry) and self._task4_is_inline(entry):
                self._task_mat_words[slot] = self._clone_word(entry, 0)
                self._task_mat_valid[slot] = 1
                self._task_stack_f[sp] = index + 1
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_MAT_STRUCT_SCAN:
            cursor = self._task_stack_a[sp]
            environment = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            requested_head = self._task_stack_d[sp]
            slots = self._task_stack_e[sp]
            count = self._task_stack_f[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor = self._task_memory[cursor]
            if descriptor == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(descriptor)
            if opcode == abi.MOP_VAR:
                variable = self._signed_data(descriptor)
                if variable != 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                if not self._task4_mat_append(
                    self._make_word(
                        abi.MOP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(0),
                        requested_head,
                    )
                ):
                    return
                self._task_sp -= 1
                if not self._task4_push(
                    TASK4_MAT_STRUCT_PROCESS,
                    cursor - count,
                    environment,
                    depth,
                    slots,
                    count,
                    0,
                ):
                    return
                return
            if (
                opcode == abi.MOP_APP
                or opcode == abi.MOP_APP_VAR
                or (not self._head(descriptor) and self._task4_is_inline(descriptor))
            ):
                if self._task_mat_count >= len(self._task_mat_words):
                    self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                    return
                self._task_mat_valid[self._task_mat_count] = 0
                self._task_mat_count += 1
                self._task_stack_a[sp] = cursor + 1
                self._task_stack_f[sp] = count + 1
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_MAT_STRUCT_PROCESS:
            source_start = self._task_stack_a[sp]
            environment = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            slots = self._task_stack_d[sp]
            count = self._task_stack_e[sp]
            index = self._task_stack_f[sp]
            if index >= count:
                self._task_sp -= 1
                return
            source = source_start + index
            slot = slots + index
            if source < 0 or source >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if slot < 0 or slot >= len(self._task_mat_words):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor = self._task_memory[source]
            if descriptor == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(descriptor)
            if opcode == abi.MOP_APP:
                target = self._signed_data(descriptor)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_mat_count),
                    0,
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_f[sp] = index + 1
                self._task4_push(TASK4_MAT_GRAPH, target, environment, depth, 1)
                return
            if opcode == abi.MOP_APP_VAR:
                variable = self._signed_data(descriptor)
                if variable is None or variable < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(variable),
                    0,
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_f[sp] = index + 1
                return
            if not self._head(descriptor) and self._task4_is_inline(descriptor):
                target = self._task_mat_count
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(target),
                    0,
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_f[sp] = index + 1
                self._task4_mat_append(self._clone_word(descriptor, 1))
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_MAT_LAMBDA_SCAN:
            cursor = self._task_stack_a[sp]
            environment = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            requested_head = self._task_stack_d[sp]
            count = self._task_stack_e[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word != 0 and self._opcode(word) == abi.MOP_LAMBDA:
                if not self._task4_mat_append(
                    self._make_word(
                        abi.MOP_LAMBDA,
                        self._data_kind(word),
                        self._payload(word),
                        0,
                        self._definition_valid(word),
                        self._definition(word),
                    )
                ):
                    return
                self._task_stack_a[sp] = cursor + 1
                self._task_stack_e[sp] = count + 1
                return
            self._task_sp -= 1
            self._task4_push(
                TASK4_MAT_GRAPH,
                cursor,
                environment,
                depth + count,
                requested_head,
            )
            return

        if kind == TASK4_MAT_LOOKUP:
            address = self._task_stack_a[sp]
            remaining = self._task_stack_b[sp]
            head = self._task_stack_c[sp]
            depth = self._task_stack_d[sp]
            mode = self._task_stack_e[sp]
            slot = self._task_stack_f[sp]
            source = self._task_stack_g[sp]
            hops = self._task_stack_h[sp]
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[address]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if opcode == abi.MOP_PNP:
                parent = self._signed_data(word)
                if parent is None or parent < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                hops += 1
                if hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_a[sp] = parent
                self._task_stack_h[sp] = hops
                return
            if remaining == 0:
                self._task_sp -= 1
                if mode == 1 and self._is_shareable_atomic(word):
                    self._task_mat_words[slot] = self._clone_word(word, 0)
                    self._task_mat_valid[slot] = 1
                    return
                if mode == 1:
                    source_word = self._task_memory[source]
                    self._task_mat_words[slot] = self._make_word(
                        abi.MOP_APP,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(self._task_mat_count),
                        0,
                        self._definition_valid(source_word),
                        self._definition(source_word),
                    )
                    self._task_mat_valid[slot] = 1
                    head = 1
                self._task4_push(TASK4_MAT_ENV_CHASE, address, head, depth, 0)
                return
            self._task_stack_b[sp] = remaining - 1
            if opcode == abi.MOP_REC:
                self._task_stack_a[sp] = address + 3
            elif opcode == abi.MOP_CLOSURE or self._closure_slot(word):
                self._task_stack_a[sp] = address + 2
            else:
                self._task_stack_a[sp] = address + 1
            return

        if kind == TASK4_MAT_ENV_CHASE:
            address = self._task_stack_a[sp]
            head = self._task_stack_b[sp]
            depth = self._task_stack_c[sp]
            hops = self._task_stack_d[sp]
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[address]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if opcode == abi.MOP_EP:
                target = self._signed_data(word)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                hops += 1
                if hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_a[sp] = target
                self._task_stack_d[sp] = hops
                return
            self._task_sp -= 1
            if self._is_shareable_atomic(word):
                self._task4_mat_append(self._clone_word(word, head))
                return
            if opcode == abi.MOP_CLOSURE:
                self._task4_push(TASK4_MAT_CLOSURE, address, head)
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task4_publication_clock(self) -> None:
        if self._task_sp < 0:
            return
        sp = self._task_sp
        kind = self._task_stack_kind[sp]
        if (
            TASK4_MAT_GRAPH <= kind <= TASK4_MAT_VISIT_SCAN
            or kind == TASK4_MAT_STRUCT_SCAN
            or kind == TASK4_MAT_STRUCT_PROCESS
        ):
            self._task4_materialization_clock(kind)
            return

        if kind == TASK4_PUB_ROOT_DONE:
            root = self._task_stack_a[sp]
            if root < 0 or root >= len(self._task_pub_root_state):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_pub_root_state[root] = 2
            self._task_pub_root_result[root] = self._task_pub_value
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_GRAPH:
            address = self._task_stack_a[sp]
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            state = self._task_pub_root_state[address]
            if state == 2:
                self._task_pub_value = self._task_pub_root_result[address]
                self._task_sp -= 1
                return
            if state == 1:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            word = self._task_memory[address]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_pub_root_state[address] = 1
            self._task_sp -= 1
            if not self._task4_push(TASK4_PUB_ROOT_DONE, address):
                return
            opcode = self._opcode(word)
            if opcode == abi.MOP_EP:
                target = self._signed_data(word)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task4_push(TASK4_PUB_EP_CHASE, address, target, 0, 0)
                return
            if self._task4_is_app_prefix(word):
                self._task4_push(TASK4_PUB_APP_SCAN, address, address)
                return
            if opcode == abi.MOP_LAMBDA:
                self._task4_push(TASK4_PUB_LAMBDA_SCAN, address, address)
                return
            if opcode == abi.MOP_RBLOCK:
                self._task4_push(TASK4_PUB_RBLOCK_SCAN, address, address, 0)
                return
            if opcode == abi.MOP_STRUCT:
                self._task4_push(TASK4_PUB_STRUCT_SCAN, address, address + 1)
                return
            self._task_pub_value = address
            return

        if kind == TASK4_PUB_APP_SCAN:
            root = self._task_stack_a[sp]
            cursor = self._task_stack_b[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            entry = self._task_memory[cursor]
            if entry == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(entry)
            if opcode == abi.MOP_APP:
                target = self._signed_data(entry)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_sp -= 1
                if not self._task4_push(TASK4_PUB_APP_SCAN, root, cursor + 1):
                    return
                if not self._task4_push(TASK4_PUB_APP_REWRITE, cursor, target):
                    return
                self._task4_push(TASK4_PUB_GRAPH, target)
                return
            if opcode == abi.MOP_APP_VAR or (
                not self._head(entry) and self._task4_is_inline(entry)
            ):
                self._task_stack_b[sp] = cursor + 1
                return
            self._task_sp -= 1
            if not self._task4_push(TASK4_PUB_APP_OPERATOR_DONE, root, cursor):
                return
            self._task4_push(TASK4_PUB_GRAPH, cursor)
            return

        if kind == TASK4_PUB_APP_REWRITE:
            descriptor_address = self._task_stack_a[sp]
            original_target = self._task_stack_b[sp]
            descriptor = self._task_memory[descriptor_address]
            if self._task_pub_value != original_target:
                self._task_memory[descriptor_address] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_pub_value),
                    self._head(descriptor),
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_APP_OPERATOR_DONE:
            root = self._task_stack_a[sp]
            operator = self._task_stack_b[sp]
            if self._task_pub_value != operator:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_pub_value = root
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_LAMBDA_SCAN:
            root = self._task_stack_a[sp]
            cursor = self._task_stack_b[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word != 0 and self._opcode(word) == abi.MOP_LAMBDA:
                self._task_stack_b[sp] = cursor + 1
                return
            self._task_sp -= 1
            if not self._task4_push(TASK4_PUB_LAMBDA_DONE, root, cursor):
                return
            self._task4_push(TASK4_PUB_GRAPH, cursor)
            return

        if kind == TASK4_PUB_LAMBDA_DONE:
            root = self._task_stack_a[sp]
            body = self._task_stack_b[sp]
            if self._task_pub_value != body:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_pub_value = root
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_RBLOCK_SCAN:
            root = self._task_stack_a[sp]
            cursor = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(word) == abi.MOP_RBLOCK:
                binding_address = self._signed_data(word)
                if binding_address is None or binding_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                binding_root = binding_address + 1
                if binding_root < 0 or binding_root >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_sp -= 1
                if not self._task4_push(
                    TASK4_PUB_RBLOCK_SCAN,
                    root,
                    cursor + 1,
                    count + 1,
                ):
                    return
                if not self._task4_push(
                    TASK4_PUB_RBLOCK_BINDING_DONE,
                    binding_root,
                ):
                    return
                self._task4_push(TASK4_PUB_GRAPH, binding_root)
                return
            rup_count = self._signed_data(word)
            if self._opcode(word) != abi.MOP_RUP or rup_count != count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            body = cursor + 1
            if body < 0 or body >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_sp -= 1
            if not self._task4_push(TASK4_PUB_RBLOCK_BODY_DONE, root, body):
                return
            self._task4_push(TASK4_PUB_GRAPH, body)
            return

        if kind == TASK4_PUB_RBLOCK_BINDING_DONE:
            binding_root = self._task_stack_a[sp]
            if self._task_pub_value != binding_root:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_RBLOCK_BODY_DONE:
            root = self._task_stack_a[sp]
            body = self._task_stack_b[sp]
            if self._task_pub_value != body:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_pub_value = root
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_STRUCT_SCAN:
            root = self._task_stack_a[sp]
            cursor = self._task_stack_b[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor = self._task_memory[cursor]
            if descriptor == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(descriptor)
            if opcode == abi.MOP_APP:
                target = self._signed_data(descriptor)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_stack_b[sp] = cursor + 1
                if not self._task4_push(TASK4_PUB_APP_REWRITE, cursor, target):
                    return
                self._task4_push(TASK4_PUB_GRAPH, target)
                return
            if opcode == abi.MOP_EP:
                target = self._signed_data(descriptor)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_stack_b[sp] = cursor + 1
                self._task4_push(TASK4_PUB_EP_CHASE, cursor, target, 0, 1)
                return
            if opcode == abi.MOP_APP_VAR or (
                not self._head(descriptor) and self._task4_is_inline(descriptor)
            ):
                self._task_stack_b[sp] = cursor + 1
                return
            selector = self._signed_data(descriptor)
            if opcode != abi.MOP_VAR or selector != 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_pub_value = root
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_REC:
            rec_address = self._task_stack_a[sp]
            if rec_address < 0 or rec_address + 2 >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task_pub_rec_valid[rec_address]:
                self._task_pub_value = self._task_pub_rec_result[rec_address]
                self._task_sp -= 1
                return
            rec = self._task_memory[rec_address]
            context_word = self._task_memory[rec_address + 1]
            block_word = self._task_memory[rec_address + 2]
            if rec == 0 or self._opcode(rec) != abi.MOP_REC:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if context_word == 0 or block_word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(context_word) != abi.MOP_NONE or self._opcode(block_word) != abi.MOP_NONE:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            context = self._signed_data(context_word)
            block_address = self._signed_data(block_word)
            binding_address = self._signed_data(rec)
            if (
                context is None
                or context < 0
                or block_address is None
                or block_address < 0
                or binding_address is None
                or binding_address < 0
            ):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_stack_kind[sp] = TASK4_PUB_REC_SCAN
            self._task_stack_b[sp] = context
            self._task_stack_c[sp] = block_address
            self._task_stack_d[sp] = block_address
            self._task_stack_e[sp] = 0
            return

        if kind == TASK4_PUB_REC_SCAN:
            rec_address = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            cursor = self._task_stack_d[sp]
            count = self._task_stack_e[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(word) == abi.MOP_RBLOCK:
                binding_address = self._signed_data(word)
                if binding_address is None or binding_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                count += 1
                if count > len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_d[sp] = cursor + 1
                self._task_stack_e[sp] = count
                return
            rup_count = self._signed_data(word)
            if count == 0 or self._opcode(word) != abi.MOP_RUP or rup_count != count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            selected_delta = rec_address - context
            if selected_delta < 0 or selected_delta % 3 != 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            selected = selected_delta // 3
            if selected >= count:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_stack_kind[sp] = TASK4_PUB_REC_BINDINGS
            self._task_stack_d[sp] = count
            self._task_stack_e[sp] = 0
            self._task_stack_f[sp] = selected
            self._task_stack_g[sp] = 0
            return

        if kind == TASK4_PUB_REC_BINDINGS:
            rec_address = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            count = self._task_stack_d[sp]
            index = self._task_stack_e[sp]
            selected = self._task_stack_f[sp]
            stage = self._task_stack_g[sp]
            if index >= count:
                destination = self._task_fsp + 1
                last = destination + count + 1
                if destination < 0 or last >= self._task_free_space or last >= len(self._task_memory):
                    self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                    return
                self._task_stack_kind[sp] = TASK4_PUB_REC_WRITE
                self._task_stack_b[sp] = block_address
                self._task_stack_c[sp] = count
                self._task_stack_d[sp] = selected
                self._task_stack_e[sp] = destination
                self._task_stack_f[sp] = 0
                return
            source = block_address + index
            if source < 0 or source >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            block = self._task_memory[source]
            if block == 0 or self._opcode(block) != abi.MOP_RBLOCK:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            binding_address = self._signed_data(block)
            if binding_address is None or binding_address < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if binding_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            name = self._task_memory[binding_address]
            if (
                name == 0
                or self._opcode(name) != abi.MOP_SYM
                or self._data_kind(name) != abi.DATA_LITERAL_ID
                or self._payload(name) == 0
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            binding_root = binding_address + 1
            if binding_root < 0 or binding_root >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if stage == 0:
                self._task_mat_visit_count = 0
                self._task_stack_g[sp] = 1
                self._task4_push(
                    TASK4_PUB_REC_RW_GRAPH,
                    binding_root,
                    context,
                    block_address,
                    count,
                    0,
                )
                return
            if stage == 1:
                if self._task_mat_visit_count != 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_g[sp] = 2
                self._task4_push(TASK4_PUB_GRAPH, binding_root)
                return
            if stage == 2:
                if self._task_pub_value != binding_root:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_e[sp] = index + 1
                self._task_stack_g[sp] = 0
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_PUB_REC_WRITE:
            rec_address = self._task_stack_a[sp]
            block_address = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            selected = self._task_stack_d[sp]
            destination = self._task_stack_e[sp]
            index = self._task_stack_f[sp]
            last = destination + count + 1
            if destination < 0 or last >= self._task_free_space or last >= len(self._task_memory):
                self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                return
            if index < count:
                source = block_address + index
                if source < 0 or source >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                block = self._task_memory[source]
                if block == 0 or self._opcode(block) != abi.MOP_RBLOCK:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_memory[destination + index] = self._make_word(
                    abi.MOP_RBLOCK,
                    self._data_kind(block),
                    self._payload(block),
                    0,
                    self._definition_valid(block),
                    self._definition(block),
                )
                self._task_stack_f[sp] = index + 1
                return
            if index == count:
                self._task_memory[destination + index] = self._make_word(
                    abi.MOP_RUP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(count),
                    0,
                )
                self._task_stack_f[sp] = index + 1
                return
            if index == count + 1:
                self._task_memory[destination + index] = self._make_word(
                    abi.MOP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(selected),
                    1,
                )
                self._task_fsp = last
                self._task_pub_rec_valid[rec_address] = 1
                self._task_pub_rec_result[rec_address] = destination
                self._task_pub_root_state[destination] = 2
                self._task_pub_root_result[destination] = destination
                self._task_pub_value = destination
                self._task_sp -= 1
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_PUB_REC_RW_LEAVE:
            expected = self._task_stack_a[sp]
            if self._task_mat_visit_count <= 0 or self._task_mat_visit_count - 1 != expected:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_mat_visit_count -= 1
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_REC_RW_GRAPH:
            address = self._task_stack_a[sp]
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task_memory[address] == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_stack_kind[sp] = TASK4_PUB_REC_RW_VISIT_SCAN
            self._task_stack_f[sp] = 0
            return

        if kind == TASK4_PUB_REC_RW_VISIT_SCAN:
            address = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            count = self._task_stack_d[sp]
            depth = self._task_stack_e[sp]
            visit_index = self._task_stack_f[sp]
            if visit_index < self._task_mat_visit_count:
                if (
                    self._task_mat_visit_address[visit_index] == address
                    and self._task_mat_visit_environment[visit_index] == context
                    and self._task_mat_visit_depth[visit_index] == depth
                ):
                    self._task_sp -= 1
                    return
                self._task_stack_f[sp] = visit_index + 1
                return
            if self._task_mat_visit_count >= len(self._task_mat_visit_address):
                self._fault(abi.FAULT_CONTROL_OVERFLOW)
                return
            active = self._task_mat_visit_count
            self._task_mat_visit_address[active] = address
            self._task_mat_visit_environment[active] = context
            self._task_mat_visit_depth[active] = depth
            self._task_mat_visit_head[active] = 0
            self._task_mat_visit_count += 1
            word = self._task_memory[address]
            opcode = self._opcode(word)
            self._task_sp -= 1
            if not self._task4_push(TASK4_PUB_REC_RW_LEAVE, active):
                return
            if opcode == abi.MOP_EP:
                target = self._signed_data(word)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task4_push(
                    TASK4_PUB_REC_RW_EP_CHASE,
                    address,
                    target,
                    context,
                    block_address,
                    count,
                    depth,
                    0,
                )
                return
            if self._task4_is_app_prefix(word):
                self._task4_push(
                    TASK4_PUB_REC_RW_APP_SCAN,
                    address,
                    context,
                    block_address,
                    count,
                    depth,
                )
                return
            if opcode == abi.MOP_RBLOCK:
                self._task4_push(
                    TASK4_PUB_REC_RW_RBLOCK,
                    address,
                    context,
                    block_address,
                    count,
                    depth,
                    0,
                    0,
                    0,
                )
                return
            if opcode == abi.MOP_LAMBDA:
                self._task4_push(
                    TASK4_PUB_REC_RW_LAMBDA_SCAN,
                    address,
                    context,
                    block_address,
                    count,
                    depth,
                )
                return
            if opcode == abi.MOP_STRUCT:
                self._task4_push(
                    TASK4_PUB_REC_RW_STRUCT,
                    address + 1,
                    context,
                    block_address,
                    count,
                    depth + 1,
                )
                return
            return

        if kind == TASK4_PUB_REC_RW_STRUCT:
            cursor = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            count = self._task_stack_d[sp]
            depth = self._task_stack_e[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor = self._task_memory[cursor]
            if descriptor == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(descriptor)
            if opcode == abi.MOP_APP:
                target = self._signed_data(descriptor)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_stack_a[sp] = cursor + 1
                self._task4_push(
                    TASK4_PUB_REC_RW_GRAPH,
                    target,
                    context,
                    block_address,
                    count,
                    depth,
                )
                return
            if opcode == abi.MOP_EP:
                self._task_stack_a[sp] = cursor + 1
                self._task4_push(
                    TASK4_PUB_REC_RW_GRAPH,
                    cursor,
                    context,
                    block_address,
                    count,
                    depth,
                )
                return
            if opcode == abi.MOP_APP_VAR or (
                not self._head(descriptor) and self._task4_is_inline(descriptor)
            ):
                self._task_stack_a[sp] = cursor + 1
                return
            selector = self._signed_data(descriptor)
            if opcode != abi.MOP_VAR or selector != 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_REC_RW_EP_CHASE:
            descriptor_address = self._task_stack_a[sp]
            target_address = self._task_stack_b[sp]
            context = self._task_stack_c[sp]
            block_address = self._task_stack_d[sp]
            count = self._task_stack_e[sp]
            depth = self._task_stack_f[sp]
            hops = self._task_stack_g[sp]
            if target_address < 0 or target_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            target = self._task_memory[target_address]
            if target == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(target) == abi.MOP_EP:
                next_address = self._signed_data(target)
                if next_address is None or next_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                hops += 1
                if hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_b[sp] = next_address
                self._task_stack_g[sp] = hops
                return
            if self._opcode(target) == abi.MOP_REC:
                if target_address + 2 >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                target_binding = self._signed_data(target)
                if target_binding is None or target_binding < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                target_context_word = self._task_memory[target_address + 1]
                target_block_word = self._task_memory[target_address + 2]
                if target_context_word == 0 or target_block_word == 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if (
                    self._opcode(target_context_word) != abi.MOP_NONE
                    or self._opcode(target_block_word) != abi.MOP_NONE
                ):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                target_context = self._signed_data(target_context_word)
                target_block = self._signed_data(target_block_word)
                if target_context is None or target_block is None:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if target_context == context and target_block == block_address:
                    delta = target_address - context
                    if delta < 0 or delta % 3 != 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    index = delta // 3
                    if index >= count:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    descriptor = self._task_memory[descriptor_address]
                    self._task_memory[descriptor_address] = self._make_word(
                        abi.MOP_VAR if self._head(descriptor) else abi.MOP_APP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(index + depth),
                        self._head(descriptor),
                        self._definition_valid(descriptor),
                        self._definition(descriptor),
                    )
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_REC_RW_APP_SCAN:
            cursor = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            count = self._task_stack_d[sp]
            depth = self._task_stack_e[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            entry = self._task_memory[cursor]
            if entry == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(entry)
            if opcode == abi.MOP_APP:
                target = self._signed_data(entry)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_stack_a[sp] = cursor + 1
                self._task4_push(
                    TASK4_PUB_REC_RW_GRAPH,
                    target,
                    context,
                    block_address,
                    count,
                    depth,
                )
                return
            if opcode == abi.MOP_EP and not self._head(entry):
                self._task_stack_a[sp] = cursor + 1
                self._task4_push(
                    TASK4_PUB_REC_RW_GRAPH,
                    cursor,
                    context,
                    block_address,
                    count,
                    depth,
                )
                return
            if opcode == abi.MOP_APP_VAR or (
                not self._head(entry) and self._task4_is_inline(entry)
            ):
                self._task_stack_a[sp] = cursor + 1
                return
            self._task_sp -= 1
            self._task4_push(
                TASK4_PUB_REC_RW_GRAPH,
                cursor,
                context,
                block_address,
                count,
                depth,
            )
            return

        if kind == TASK4_PUB_REC_RW_LAMBDA_SCAN:
            cursor = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            count = self._task_stack_d[sp]
            depth = self._task_stack_e[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word != 0 and self._opcode(word) == abi.MOP_LAMBDA:
                self._task_stack_a[sp] = cursor + 1
                self._task_stack_e[sp] = depth + 1
                return
            self._task_sp -= 1
            self._task4_push(
                TASK4_PUB_REC_RW_GRAPH,
                cursor,
                context,
                block_address,
                count,
                depth,
            )
            return

        if kind == TASK4_PUB_REC_RW_RBLOCK:
            start = self._task_stack_a[sp]
            context = self._task_stack_b[sp]
            block_address = self._task_stack_c[sp]
            outer_count = self._task_stack_d[sp]
            depth = self._task_stack_e[sp]
            nested_count = self._task_stack_f[sp]
            index = self._task_stack_g[sp]
            stage = self._task_stack_h[sp]
            cursor = start + nested_count
            if stage == 0:
                if cursor < 0 or cursor >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                word = self._task_memory[cursor]
                if word == 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if self._opcode(word) == abi.MOP_RBLOCK:
                    binding_address = self._signed_data(word)
                    if binding_address is None or binding_address < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    nested_count += 1
                    if nested_count > len(self._task_memory):
                        self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                        return
                    self._task_stack_f[sp] = nested_count
                    return
                rup_count = self._signed_data(word)
                if nested_count == 0 or self._opcode(word) != abi.MOP_RUP or rup_count != nested_count:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_g[sp] = 0
                self._task_stack_h[sp] = 1
                return
            nested_depth = depth + nested_count
            if stage == 1:
                if index < nested_count:
                    nested = self._task_memory[start + index]
                    binding_address = self._signed_data(nested) if nested else None
                    if nested == 0 or self._opcode(nested) != abi.MOP_RBLOCK or binding_address is None or binding_address < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    self._task_stack_g[sp] = index + 1
                    self._task4_push(
                        TASK4_PUB_REC_RW_GRAPH,
                        binding_address + 1,
                        context,
                        block_address,
                        outer_count,
                        nested_depth,
                    )
                    return
                self._task_stack_h[sp] = 2
                return
            if stage == 2:
                self._task_stack_h[sp] = 3
                self._task4_push(
                    TASK4_PUB_REC_RW_GRAPH,
                    start + nested_count + 1,
                    context,
                    block_address,
                    outer_count,
                    nested_depth,
                )
                return
            if stage == 3:
                self._task_sp -= 1
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_PUB_EP_CHASE:
            descriptor_address = self._task_stack_a[sp]
            target_address = self._task_stack_b[sp]
            hops = self._task_stack_c[sp]
            embedded = self._task_stack_d[sp]
            if target_address < 0 or target_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            target = self._task_memory[target_address]
            if target == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(target) == abi.MOP_EP:
                next_address = self._signed_data(target)
                if next_address is None or next_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                hops += 1
                if hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_b[sp] = next_address
                self._task_stack_c[sp] = hops
                return
            if not self._task_interval_start <= target_address < self._task_interval_stop:
                self._task_pub_value = descriptor_address
                self._task_sp -= 1
                return
            descriptor = self._task_memory[descriptor_address]
            if self._is_shareable_atomic(target):
                self._task_memory[descriptor_address] = self._make_word(
                    self._opcode(target),
                    self._data_kind(target),
                    self._payload(target),
                    self._head(descriptor),
                    self._definition_valid(target),
                    self._definition(target),
                )
                self._task_pub_value = descriptor_address
                self._task_sp -= 1
                return
            target_opcode = self._opcode(target)
            if target_opcode == abi.MOP_UBV:
                binder = self._signed_data(target)
                if binder is None:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                index = self._task_phi - binder
                if index < 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_memory[descriptor_address] = self._make_word(
                    abi.MOP_APP_VAR if embedded else abi.MOP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(index),
                    self._head(descriptor),
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
                self._task_pub_value = descriptor_address
                self._task_sp -= 1
                return
            if target_opcode == abi.MOP_CLOSURE:
                self._task_sp -= 1
                if not self._task4_push(
                    TASK4_PUB_EP_CLOSURE_DONE,
                    descriptor_address,
                    embedded,
                ):
                    return
                self._task4_push(TASK4_PUB_CLOSURE, target_address)
                return
            if target_opcode == abi.MOP_REC:
                self._task_sp -= 1
                if not self._task4_push(
                    TASK4_PUB_EP_CLOSURE_DONE,
                    descriptor_address,
                    embedded,
                ):
                    return
                self._task4_push(TASK4_PUB_REC, target_address)
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK4_PUB_EP_CLOSURE_DONE:
            descriptor_address = self._task_stack_a[sp]
            embedded = self._task_stack_b[sp]
            if embedded:
                descriptor = self._task_memory[descriptor_address]
                self._task_memory[descriptor_address] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_pub_value),
                    self._head(descriptor),
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
            self._task_sp -= 1
            return

        if kind == TASK4_PUB_CLOSURE:
            closure_address = self._task_stack_a[sp]
            if closure_address < 0 or closure_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task_pub_closure_valid[closure_address]:
                self._task_pub_value = self._task_pub_closure_result[closure_address]
                self._task_sp -= 1
                return
            self._task_mat_count = 0
            self._task_mat_visit_count = 0
            destination = self._task_fsp + 1
            self._task_sp -= 1
            if not self._task4_push(
                TASK4_PUB_CLOSURE_WRITE,
                closure_address,
                destination,
                0,
            ):
                return
            self._task4_push(TASK4_MAT_CLOSURE, closure_address, -1)
            return

        if kind == TASK4_PUB_CLOSURE_WRITE:
            closure_address = self._task_stack_a[sp]
            destination = self._task_stack_b[sp]
            index = self._task_stack_c[sp]
            if self._task_mat_count <= 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            last = destination + self._task_mat_count - 1
            if destination < 0 or last >= self._task_free_space:
                self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                return
            if last >= len(self._task_memory):
                self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                return
            if index < self._task_mat_count:
                if not self._task_mat_valid[index]:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                graph_word = self._task_mat_words[index]
                if self._opcode(graph_word) == abi.MOP_APP:
                    relative = self._signed_data(graph_word)
                    if relative is None or relative < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    graph_word = self._make_word(
                        abi.MOP_APP,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(destination + relative),
                        self._head(graph_word),
                        self._definition_valid(graph_word),
                        self._definition(graph_word),
                    )
                self._task_memory[destination + index] = graph_word
                self._task_stack_c[sp] = index + 1
                return
            self._task_fsp = last
            self._task_pub_closure_valid[closure_address] = 1
            self._task_pub_closure_result[closure_address] = destination
            self._task_pub_root_state[destination] = 2
            self._task_pub_root_result[destination] = destination
            self._task_pub_value = destination
            self._task_sp -= 1
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task4_join_restore_and_commit(self, parent_address: int) -> None:
        self._task_free_space = self._task_frame_free_space
        self._task_env = self._task_frame_env
        if self._task_saved_primitive:
            self._task_prim_id = self._task_frame_prim_id
            self._task_fire = self._task_frame_fire - 1
            if self._task_fire == 0:
                self._task_pc = parent_address
                if not self._task4_fire_primitive():
                    return
                self.microstate = MICRO_COMMIT
                return
        self._task_pc = parent_address - 1
        self.microstate = MICRO_COMMIT

    def _task4_join_clock(self) -> None:
        if self._task4_phase == TASK4_JOIN_INIT:
            if self._task_direction != abi.DIRECTION_REVERSE:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_pc < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[self._task_pc]
            parent_address = self._signed_data(word)
            if parent_address is None or parent_address < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if parent_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            result_address = self._task_pc + 1
            if result_address < 0 or result_address > self._task_fsp:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            parent = self._task_memory[parent_address]
            if parent == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            parent_opcode = self._opcode(parent)
            if parent_opcode not in (
                abi.MOP_APP,
                abi.MOP_EP,
                abi.MOP_RBLOCK,
                abi.MOP_RECP,
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if parent_opcode == abi.MOP_EP:
                target_address = self._signed_data(parent)
                if target_address is None or target_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if target_address >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                target = self._task_memory[target_address]
                if target == 0 or self._opcode(target) != abi.MOP_CLOSURE:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
            self._task_parent_address = parent_address
            self._task_result_address = result_address
            self._task_saved_primitive = int(
                self._definition_valid(word) != 0 and self._definition(word) == 1
            )
            self._task_frame_index = self._task_c
            self._task4_phase = TASK4_JOIN_FIND_FRAME
            return

        if self._task4_phase == TASK4_JOIN_FIND_FRAME:
            frame_index = self._task_frame_index
            if frame_index < 0 or frame_index >= len(self._task_control):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            entry = self._task_control[frame_index]
            if type(entry) is not int or entry < 0 or entry >= (1 << abi.CONTROL_WIDTH):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            tag = abi.control_tag(entry)
            if tag == abi.CONTROL_SAVED_DEFINITION_PATH:
                self._task_control[frame_index] = 0
                self._task_c = frame_index - 1
                self._task_frame_index = frame_index - 1
                return
            if tag != abi.CONTROL_SUBGRAPH:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            frame_env = abi.control_field(entry, 0)
            frame_free_space = abi.control_field(entry, 1)
            frame_prim_id = abi.control_field(entry, 2)
            frame_fire = abi.control_field(entry, 3)
            if self._task_saved_primitive and (frame_prim_id == 0 or frame_fire <= 0):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            current_frontier = self._task_free_space
            if current_frontier < 0 or current_frontier > frame_free_space:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if frame_free_space > len(self._task_memory):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if frame_env < 0 or frame_env > len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if current_frontier <= frame_env < frame_free_space:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_control[frame_index] = 0
            self._task_c = frame_index - 1
            self._task_frame_env = frame_env
            self._task_frame_free_space = frame_free_space
            self._task_frame_prim_id = frame_prim_id
            self._task_frame_fire = frame_fire
            self._task_interval_start = current_frontier
            self._task_interval_stop = frame_free_space
            if not self._task4_start_publication(self._task_result_address):
                return
            self._task4_phase = TASK4_JOIN_PUBLISH
            return

        if self._task4_phase == TASK4_JOIN_PUBLISH:
            if self._task_sp >= 0:
                self._task4_publication_clock()
                return
            self._task_published_result = self._task_pub_value
            self._task4_phase = TASK4_JOIN_FINISH
            return

        if self._task4_phase == TASK4_JOIN_FINISH:
            parent_address = self._task_parent_address
            parent = self._task_memory[parent_address]
            parent_opcode = self._opcode(parent)
            self._task_s_a = self._task_published_result
            self._task_s_a_valid = 1
            if self._task_s_a < 0 or self._task_s_a > self._task_fsp:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            tail = self._task_memory[self._task_s_a]
            if tail == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            single_word = self._task_fsp == self._task_s_a
            shareable_atomic = (
                single_word
                and self._head(tail) != 0
                and self._is_shareable_atomic(tail)
            )
            tail_opcode = self._opcode(tail)
            if parent_opcode == abi.MOP_RBLOCK:
                self._task_memory[parent_address] = self._make_word(
                    abi.MOP_RBLOCK,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_s_a),
                    self._head(parent),
                    self._definition_valid(parent),
                    self._definition(parent),
                )
                previous_is_rblock = False
                if parent_address > 0:
                    previous = self._task_memory[parent_address - 1]
                    previous_is_rblock = previous != 0 and self._opcode(previous) == abi.MOP_RBLOCK
                if self._task_q == 0 and not previous_is_rblock:
                    self._task_join_cursor = parent_address + 1
                    self._task_join_count = 1
                    self._task4_phase = TASK4_JOIN_RBLOCK_PHI
                    return
            elif parent_opcode == abi.MOP_RECP:
                self._task_memory[parent_address] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_s_a),
                    0,
                )
            elif single_word and self._head(tail) != 0 and tail_opcode == abi.MOP_VAR:
                index = self._signed_data(tail)
                if index is None or index < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_memory[parent_address] = self._make_word(
                    abi.MOP_VAR if self._head(parent) else abi.MOP_APP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(index),
                    self._head(parent),
                )
                if self._head(parent):
                    self._task_fsp = parent_address
                else:
                    self._task_fsp -= 2
            elif single_word and self._head(tail) != 0 and tail_opcode == abi.MOP_APP:
                app_target = self._signed_data(tail)
                if app_target is None or app_target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_memory[parent_address] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(app_target),
                    self._head(parent),
                    self._definition_valid(tail),
                    self._definition(tail),
                )
            elif parent_opcode == abi.MOP_EP and shareable_atomic:
                target_address = self._signed_data(parent)
                if target_address is None or target_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if target_address >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_memory[target_address] = self._make_word(
                    self._opcode(tail),
                    self._data_kind(tail),
                    self._payload(tail),
                    0,
                    self._definition_valid(tail),
                    self._definition(tail),
                    1,
                )
                self._task_memory[parent_address] = self._clone_word(tail, 0)
                self._task_fsp -= 2
            elif shareable_atomic:
                self._task_memory[parent_address] = self._make_word(
                    self._opcode(tail),
                    self._data_kind(tail),
                    self._payload(tail),
                    self._head(parent),
                    self._definition_valid(tail),
                    self._definition(tail),
                )
                if self._head(parent):
                    self._task_fsp = parent_address
                else:
                    self._task_fsp -= 2
            elif self._task_saved_primitive and single_word and tail_opcode != abi.MOP_APP:
                self._task_memory[parent_address] = self._make_word(
                    tail_opcode,
                    self._data_kind(tail),
                    self._payload(tail),
                    0,
                    self._definition_valid(tail),
                    self._definition(tail),
                )
                self._task_fsp -= 2
            else:
                self._task_memory[parent_address] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_s_a),
                    0,
                )
            self._task4_join_restore_and_commit(parent_address)
            return

        if self._task4_phase == TASK4_JOIN_RBLOCK_PHI:
            cursor = self._task_join_cursor
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            candidate = self._task_memory[cursor]
            if candidate != 0 and self._opcode(candidate) == abi.MOP_RBLOCK:
                self._task_join_count += 1
                self._task_join_cursor = cursor + 1
                if self._task_join_count > len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_phi < self._task_join_count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_phi -= self._task_join_count
            self._task4_join_restore_and_commit(self._task_parent_address)
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task4_var_clock(self) -> None:
        if self._task4_phase == TASK4_VAR_LOOKUP:
            address = self._task_var_address
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[address]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if opcode == abi.MOP_PNP:
                parent = self._signed_data(word)
                if parent is None or parent < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_var_hops += 1
                if self._task_var_hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_var_address = parent
                return
            if self._task_var_remaining == 0:
                self._task_s_a = address
                self._task_s_a_valid = 1
                self._task_s_d = 0
                self._task_s_d_valid = 1
                self._task_var_address = address
                self._task4_phase = TASK4_VAR_REDEX
                return
            self._task_var_remaining -= 1
            self._task_s_d = self._task_var_remaining
            self._task_s_d_valid = 1
            if opcode == abi.MOP_REC:
                self._task_var_address = address + 3
            elif opcode == abi.MOP_CLOSURE or self._closure_slot(word):
                self._task_var_address = address + 2
            else:
                self._task_var_address = address + 1
            return

        if self._task4_phase == TASK4_VAR_REDEX:
            redex_address = self._task_var_address
            redex = self._task_memory[redex_address]
            opcode = self._opcode(redex)
            if opcode == abi.MOP_REC:
                self._task_rec_address = redex_address
                self._task_rec_head = self._head(self._task_memory[self._task_pc])
                self._task4_kind = TASK4_RECP
                self._task4_phase = TASK4_RECP_EXEC
                return
            if opcode == abi.MOP_EP:
                target_address = self._signed_data(redex)
                if target_address is None or target_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_var_address = target_address
                self._task_var_hops = 0
                self._task4_phase = TASK4_VAR_CHASE
                return
            if self._closure_slot(redex) or self._is_shareable_atomic(redex):
                detached = self._make_word(
                    self._opcode(redex),
                    self._data_kind(redex),
                    self._payload(redex),
                    1,
                    self._definition_valid(redex),
                    self._definition(redex),
                )
                if not self._task4_task_push_result(detached):
                    return
                self._task_pc = self._task_fsp - 1
                self._task_direction = abi.DIRECTION_REVERSE
                self.microstate = MICRO_COMMIT
                return
            self._task_pc = redex_address
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase == TASK4_VAR_CHASE:
            target_address = self._task_var_address
            if target_address < 0 or target_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            target = self._task_memory[target_address]
            if target == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            target_opcode = self._opcode(target)
            if target_opcode == abi.MOP_EP:
                next_address = self._signed_data(target)
                if next_address is None or next_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_var_hops += 1
                if self._task_var_hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_var_address = next_address
                return
            if target_opcode == abi.MOP_UBV:
                binder = self._signed_data(target)
                if binder is None:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                index = self._task_phi - binder
                if index < 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                detached = self._make_word(
                    abi.MOP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(index),
                    1,
                )
                if not self._task4_task_push_result(detached):
                    return
                self._task_pc = self._task_fsp - 1
                self._task_direction = abi.DIRECTION_REVERSE
                self.microstate = MICRO_COMMIT
                return
            if target_opcode == abi.MOP_CLOSURE:
                self._task_pc = target_address
                self.microstate = MICRO_COMMIT
                return
            if self._is_shareable_atomic(target):
                detached = self._make_word(
                    self._opcode(target),
                    self._data_kind(target),
                    self._payload(target),
                    1,
                    self._definition_valid(target),
                    self._definition(target),
                )
                if not self._task4_task_push_result(detached):
                    return
                self._task_pc = self._task_fsp - 1
                self._task_direction = abi.DIRECTION_REVERSE
                self.microstate = MICRO_COMMIT
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task4_app_var_clock(self) -> None:
        if self._task4_phase == TASK4_APP_VAR_LOOKUP:
            address = self._task_var_address
            if address < 0 or address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[address]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if opcode == abi.MOP_PNP:
                parent = self._signed_data(word)
                if parent is None or parent < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_var_hops += 1
                if self._task_var_hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_var_address = parent
                return
            if self._task_var_remaining == 0:
                self._task_s_a = address
                self._task_s_a_valid = 1
                self._task_s_d = 0
                self._task_s_d_valid = 1
                self._task4_phase = TASK4_APP_VAR_REDEX
                return
            self._task_var_remaining -= 1
            self._task_s_d = self._task_var_remaining
            self._task_s_d_valid = 1
            if opcode == abi.MOP_REC:
                self._task_var_address = address + 3
            elif opcode == abi.MOP_CLOSURE or self._closure_slot(word):
                self._task_var_address = address + 2
            else:
                self._task_var_address = address + 1
            return

        if self._task4_phase == TASK4_APP_VAR_REDEX:
            redex_address = self._task_var_address
            if redex_address < 0 or redex_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            redex = self._task_memory[redex_address]
            if redex == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(redex)
            if opcode == abi.MOP_UBV:
                binder = self._signed_data(redex)
                if binder is None or binder < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                packed = self._make_word(
                    abi.MOP_APP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_phi - binder),
                    0,
                )
                if not self._task4_task_push_result(packed):
                    return
            elif opcode in (
                abi.MOP_INT,
                abi.MOP_FLOAT,
                abi.MOP_CHAR,
                abi.MOP_SYM,
                abi.MOP_PRIM_0,
                abi.MOP_PRIM_1,
                abi.MOP_PRIM_2,
            ):
                detached = self._make_word(
                    opcode,
                    self._data_kind(redex),
                    self._payload(redex),
                    0,
                    self._definition_valid(redex),
                    self._definition(redex),
                )
                if not self._task4_task_push_result(detached):
                    return
            elif opcode == abi.MOP_CLOSURE:
                captured_env = self._signed_data(redex)
                code_address = redex_address + 1
                if captured_env is None or captured_env < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if code_address < 0 or code_address >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                code = self._task_memory[code_address]
                code_target = self._signed_data(code) if code else None
                if (
                    code == 0
                    or self._opcode(code) != abi.MOP_NONE
                    or code_target is None
                    or code_target < 0
                ):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                if not self._task4_push_control_path(self._task_env):
                    return
                ep = self._make_word(
                    abi.MOP_EP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(redex_address),
                    0,
                )
                if not self._task4_task_push_result(ep):
                    return
            elif opcode == abi.MOP_EP:
                target = self._signed_data(redex)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if not self._task4_push_control_path(self._task_env):
                    return
                ep = self._make_word(
                    abi.MOP_EP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(target),
                    0,
                )
                if not self._task4_task_push_result(ep):
                    return
            elif opcode == abi.MOP_REC:
                if not self._task8_validate_rec(redex_address):
                    return
                recp = self._make_word(
                    abi.MOP_RECP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(redex_address),
                    0,
                )
                if not self._task4_task_push_result(recp):
                    return
            else:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_pc += 1
            self.microstate = MICRO_COMMIT
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task4_ep_clock(self) -> None:
        if self._task4_phase == TASK4_EP_FORWARD:
            if self._task_pc < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[self._task_pc]
            if word == 0 or self._opcode(word) != abi.MOP_EP:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if not self._task4_task_push_result(word):
                return
            if not self._task4_push_control_path(self._task_env):
                return
            self._task_pc += 1
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase == TASK4_EP_CHASE:
            target_address = self._task_ep_target
            if target_address < 0 or target_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            target = self._task_memory[target_address]
            if target == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(target) == abi.MOP_EP:
                next_address = self._signed_data(target)
                if next_address is None or next_address < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_ep_hops += 1
                if self._task_ep_hops >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_ep_target = next_address
                return
            self._task4_phase = (
                TASK4_EP_FORWARD
                if self._task_direction == abi.DIRECTION_FORWARD
                else TASK4_EP_FINISH
            )
            return

        if self._task4_phase == TASK4_EP_FINISH:
            target_address = self._task_ep_target
            target = self._task_memory[target_address]
            caller_path = self._task4_pop_control_path()
            if caller_path is None:
                return
            if caller_path != self._task_env:
                if not self._task4_push_environment_marker(caller_path):
                    return
            target_opcode = self._opcode(target)
            if target_opcode == abi.MOP_CLOSURE:
                if not self._task4_enter_subgraph(
                    self._task_env,
                    target_address,
                    self._task_ep_parent,
                ):
                    return
                self.microstate = MICRO_COMMIT
                return
            if target_opcode == abi.MOP_UBV:
                binder = self._signed_data(target)
                if binder is None:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                index = self._task_phi - binder
                if index < 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_memory[self._task_ep_parent] = self._make_word(
                    abi.MOP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(index),
                    0,
                )
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            if target_opcode in (
                abi.MOP_INT,
                abi.MOP_FLOAT,
                abi.MOP_CHAR,
                abi.MOP_SYM,
                abi.MOP_PRIM_0,
                abi.MOP_PRIM_1,
                abi.MOP_PRIM_2,
            ):
                self._task_memory[self._task_ep_parent] = self._clone_word(target, 0)
                if self._task_fire > 0:
                    if self._task_prim_id == 0:
                        self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                        return
                    self._task_fire -= 1
                    if self._task_fire == 0:
                        self._task_pc = self._task_ep_parent
                        if not self._task4_fire_primitive():
                            return
                        self.microstate = MICRO_COMMIT
                        return
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task8_validate_rec(self, address: int) -> bool:
        if address < 0 or address + 2 >= len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        rec = self._task_memory[address]
        context_word = self._task_memory[address + 1]
        block_word = self._task_memory[address + 2]
        if rec == 0 or self._opcode(rec) != abi.MOP_REC:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return False
        binding = self._signed_data(rec)
        if binding is None or binding < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        if context_word == 0 or block_word == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        if self._opcode(context_word) != abi.MOP_NONE or self._opcode(block_word) != abi.MOP_NONE:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        context = self._signed_data(context_word)
        block = self._signed_data(block_word)
        if context is None or block is None:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        self._task_rec_address = address
        self._task_rec_binding = binding
        self._task_rec_context = context
        self._task_rec_block = block
        return True

    def _task8_allocate_environment_word(self, word: int) -> bool:
        fault, _, env, free_space = abi.red2_allocate_environment(
            self._task_memory,
            self._task_fsp,
            self._task_env,
            self._task_free_space,
            word,
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_env = env
        self._task_free_space = free_space
        return True

    def _task8_allocate_rec(self, binding_address: int) -> bool:
        fault = abi._memory_layout_fault(
            self._task_memory, self._task_fsp, self._task_free_space
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        if self._task_env < 0 or self._task_env > len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        needs_bridge = self._task_free_space != self._task_env
        address = self._task_free_space - 3 - int(needs_bridge)
        if address <= self._task_fsp:
            self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
            return False
        if needs_bridge:
            self._task_memory[self._task_free_space - 1] = self._make_word(
                abi.MOP_PNP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_env),
                0,
            )
        self._task_memory[address] = self._make_word(
            abi.MOP_REC,
            abi.DATA_SIGNED,
            abi.signed_to_payload(binding_address + 1),
            0,
        )
        empty = self._make_word(abi.MOP_NONE, abi.DATA_NONE, 0, 0)
        self._task_memory[address + 1] = empty
        self._task_memory[address + 2] = empty
        self._task_env = address
        self._task_free_space = address
        return True

    def _task8_rblock_clock(self) -> None:
        if self._task4_phase != TASK4_RBLOCK_EXEC:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        word = self._task_memory[self._task_pc]
        binding = self._signed_data(word) if word else None
        if word == 0 or self._opcode(word) != abi.MOP_RBLOCK or binding is None or binding < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        if self._task_direction == abi.DIRECTION_REVERSE:
            parent_env = self._task4_pop_control_path()
            if parent_env is None:
                return
            if not self._task4_enter_subgraph(parent_env, binding, self._task_pc):
                return
            self._task_argcnt = -1
            self.microstate = MICRO_COMMIT
            return
        if self._task_q > 0:
            if not self._task8_allocate_rec(binding):
                return
        else:
            if not self._task4_task_push_result(word):
                return
            self._task_phi += 1
            ubv = self._make_word(
                abi.MOP_UBV,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_phi),
                0,
            )
            if not self._task8_allocate_environment_word(ubv):
                return
        self._task_pc += 1
        self.microstate = MICRO_COMMIT

    def _task8_rup_clock(self) -> None:
        if self._task4_phase == TASK4_RUP_INIT:
            word = self._task_memory[self._task_pc]
            count = self._signed_data(word) if word else None
            if word == 0 or self._opcode(word) != abi.MOP_RUP or count is None or count < 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_direction == abi.DIRECTION_REVERSE:
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            self._task_rec_count = count
            self._task_rec_index = 0
            self._task_rec_block = self._task_pc - count
            if self._task_q > 0:
                if self._task_rec_block < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_rec_address = self._task_env
                self._task4_phase = TASK4_RUP_SCAN
                return
            self._task4_phase = TASK4_RUP_ZERO_PUSH
            return
        if self._task4_phase == TASK4_RUP_SCAN:
            if self._task_rec_index >= self._task_rec_count:
                self._task_pc += 1
                self.microstate = MICRO_COMMIT
                return
            index = self._task_rec_index
            rec_address = self._task_rec_address + 3 * index
            source_address = self._task_rec_block + self._task_rec_count - 1 - index
            if rec_address < 0 or rec_address + 2 >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if source_address < 0 or source_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            rec = self._task_memory[rec_address]
            context_slot = self._task_memory[rec_address + 1]
            block_slot = self._task_memory[rec_address + 2]
            source = self._task_memory[source_address]
            if rec == 0 or self._opcode(rec) != abi.MOP_REC:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if context_slot == 0 or block_slot == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(context_slot) != abi.MOP_NONE or self._opcode(block_slot) != abi.MOP_NONE:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if source == 0 or self._opcode(source) != abi.MOP_RBLOCK:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            rec_binding = self._signed_data(rec)
            source_binding = self._signed_data(source)
            if rec_binding is None or rec_binding < 0 or source_binding is None or source_binding < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if rec_binding != source_binding + 1:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_memory[rec_address + 1] = self._make_word(
                abi.MOP_NONE,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_env),
                0,
            )
            self._task_memory[rec_address + 2] = self._make_word(
                abi.MOP_NONE,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_rec_block),
                0,
            )
            self._task_rec_index += 1
            return
        if self._task4_phase == TASK4_RUP_ZERO_PUSH:
            if self._task_rec_index < self._task_rec_count:
                if not self._task4_push_control_path(self._task_env):
                    return
                self._task_rec_index += 1
                return
            word = self._task_memory[self._task_pc]
            if not self._task4_task_push_result(word):
                return
            self._task_pc += 1
            self.microstate = MICRO_COMMIT
            return
        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task8_recp_clock(self) -> None:
        if self._task4_phase != TASK4_RECP_EXEC:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if not self._task8_validate_rec(self._task_rec_address):
            return
        if self._task_direction == abi.DIRECTION_FORWARD:
            if not self._task_rec_head:
                recp = self._make_word(
                    abi.MOP_RECP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_rec_address),
                    0,
                )
                if not self._task4_task_push_result(recp):
                    return
                self._task_pc += 1
                self.microstate = MICRO_COMMIT
                return
            if self._task_q == 0:
                self._task_rec_count = 0
                self._task_rec_index = 0
                self._task_rec_reverse_join = 0
                self._task4_phase = TASK4_RECP_RECON_SCAN
                return
            if not self._task4_push_environment_marker(self._task_rec_context):
                return
            self._task_pc = self._task_rec_binding
            self._task_q -= 1
            self.microstate = MICRO_COMMIT
            return
        if self._task_q == 0:
            parent_recp = self._task_pc
            if not self._task4_enter_subgraph(
                self._task_env,
                parent_recp,
                parent_recp,
            ):
                return
            self._task_rec_count = 0
            self._task_rec_index = 0
            self._task_rec_reverse_join = 1
            self._task4_phase = TASK4_RECP_RECON_SCAN
            return
        self._task_memory[self._task_pc] = self._make_word(
            abi.MOP_APP,
            abi.DATA_SIGNED,
            abi.signed_to_payload(self._task_rec_binding),
            0,
        )
        if not self._task4_push_control_path(self._task_rec_context):
            return
        self._task_q -= 1
        self.microstate = MICRO_COMMIT

    def _task8_reconstruct_clock(self) -> None:
        if self._task4_phase == TASK4_RECP_RECON_SCAN:
            cursor = self._task_rec_block + self._task_rec_count
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(word) == abi.MOP_RBLOCK:
                binding = self._signed_data(word)
                if binding is None or binding < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_rec_count += 1
                if self._task_rec_count >= len(self._task_memory):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_rec_count == 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            count = self._signed_data(word)
            if self._opcode(word) != abi.MOP_RUP or count != self._task_rec_count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            selected_delta = self._task_rec_address - self._task_rec_context
            if selected_delta < 0 or selected_delta % 3 != 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            selected = selected_delta // 3
            if selected >= self._task_rec_count:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_rec_selected = selected
            self._task_rec_index = 0
            self._task4_phase = TASK4_RECP_RECON_MARKER
            return

        if self._task4_phase == TASK4_RECP_RECON_MARKER:
            parent_environment = self._task_rec_context + 3 * self._task_rec_count
            if not self._task4_push_environment_marker(parent_environment):
                return
            self._task_rec_index = 0
            self._task4_phase = TASK4_RECP_RECON_UBV
            return

        if self._task4_phase == TASK4_RECP_RECON_UBV:
            if self._task_rec_index < self._task_rec_count:
                self._task_phi += 1
                ubv = self._make_word(
                    abi.MOP_UBV,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_phi),
                    0,
                )
                if not self._task8_allocate_environment_word(ubv):
                    return
                self._task_rec_index += 1
                return
            self._task_rec_replacement = self._task_env
            self._task_rec_index = 0
            self._task4_phase = TASK4_RECP_RECON_COPY
            return

        if self._task4_phase == TASK4_RECP_RECON_COPY:
            if self._task_rec_index < self._task_rec_count:
                source = self._task_memory[self._task_rec_block + self._task_rec_index]
                if source == 0 or self._opcode(source) != abi.MOP_RBLOCK:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                if not self._task4_task_push_result(source):
                    return
                self._task_rec_index += 1
                return
            self._task_rec_index = 0
            self._task4_phase = TASK4_RECP_RECON_PATH
            return

        if self._task4_phase == TASK4_RECP_RECON_PATH:
            if self._task_rec_index < self._task_rec_count:
                if not self._task4_push_control_path(self._task_rec_replacement):
                    return
                self._task_rec_index += 1
                return
            self._task4_phase = TASK4_RECP_RECON_FINISH
            return

        if self._task4_phase == TASK4_RECP_RECON_FINISH:
            rup = self._task_memory[self._task_rec_block + self._task_rec_count]
            if not self._task4_task_push_result(rup):
                return
            selected = self._make_word(
                abi.MOP_VAR,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_rec_selected),
                1,
            )
            if not self._task4_task_push_result(selected):
                return
            self._task_pc = self._task_fsp - 1
            self._task_direction = abi.DIRECTION_REVERSE
            self.microstate = MICRO_COMMIT
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task9_push_graph(self, word: int) -> int:
        fault, fsp, address = abi.red2_push_graph(
            self._task_memory,
            self._task_fsp,
            self._task_free_space,
            word,
        )
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return -1
        self._task_fsp = fsp
        return address

    def _task9_push_equality_frame(self, result_pc: int, live_fsp: int) -> bool:
        entry = abi.pack_control_entry(
            abi.CONTROL_EQUALITY,
            result_pc,
            live_fsp,
            0,
            0,
        )
        fault, c = abi.red2_control_push(self._task_control, self._task_c, entry)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_c = c
        return True

    def _task9_pop_equality_frame(self) -> bool:
        if self._task_c < 0 or self._task_c >= len(self._task_control):
            self._fault(abi.FAULT_CONTROL_UNDERFLOW)
            return False
        entry = self._task_control[self._task_c]
        if (
            type(entry) is not int
            or entry < 0
            or entry >= (1 << abi.CONTROL_WIDTH)
        ):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return False
        if abi.control_tag(entry) != abi.CONTROL_EQUALITY:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return False
        self._task_parent_address = abi.control_field(entry, 0)
        self._task_result_address = abi.control_field(entry, 1)
        fault, c, _ = abi.red2_control_pop(self._task_control, self._task_c)
        if fault != abi.FAULT_NONE:
            self._fault(fault)
            return False
        self._task_c = c
        return True

    def _task9_constant_class(self, word: int) -> int:
        opcode = self._opcode(word)
        kind = self._data_kind(word)
        if opcode == abi.MOP_INT and kind == abi.DATA_SIGNED:
            return 1
        if opcode == abi.MOP_FLOAT and kind == abi.DATA_FLOAT64:
            return 2
        if opcode == abi.MOP_CHAR and kind == abi.DATA_LITERAL_ID:
            return 3
        if (
            opcode in (abi.MOP_SYM, abi.MOP_PRIM_0, abi.MOP_PRIM_1, abi.MOP_PRIM_2)
            and kind == abi.DATA_LITERAL_ID
        ):
            return 4
        return 0

    def _task9_constants_equal(self, left: int, right: int) -> bool:
        left_class = self._task9_constant_class(left)
        right_class = self._task9_constant_class(right)
        if left_class == 0 or right_class == 0 or left_class != right_class:
            return False
        if left_class == 1:
            return self._signed_data(left) == self._signed_data(right)
        if left_class == 2:
            left_bits = self._payload(left)
            right_bits = self._payload(right)
            left_exp = (left_bits >> 52) & 0x7FF
            right_exp = (right_bits >> 52) & 0x7FF
            left_mantissa = left_bits & ((1 << 52) - 1)
            right_mantissa = right_bits & ((1 << 52) - 1)
            if (left_exp == 0x7FF and left_mantissa != 0) or (
                right_exp == 0x7FF and right_mantissa != 0
            ):
                return False
            if (left_bits & ((1 << 63) - 1)) == 0 and (
                right_bits & ((1 << 63) - 1)
            ) == 0:
                return True
            return left_bits == right_bits
        return self._payload(left) == self._payload(right)

    def _task9_append_task_graph(
        self,
        left: int,
        right: int,
        lambdas: int,
        descriptor_mode: int,
    ) -> int:
        if (
            self.equal_star_literal_id <= 0
            or left < 0
            or right < 0
            or lambdas < 0
            or descriptor_mode not in (0, 1)
        ):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return -1
        root = self._task_fsp + 1
        word = self._make_word(
            abi.MOP_INT,
            abi.DATA_SIGNED,
            abi.signed_to_payload(left),
            0,
        )
        if self._task9_push_graph(word) < 0:
            return -1
        word = self._make_word(
            abi.MOP_INT,
            abi.DATA_SIGNED,
            abi.signed_to_payload(right),
            0,
        )
        if self._task9_push_graph(word) < 0:
            return -1
        word = self._make_word(
            abi.MOP_INT,
            abi.DATA_SIGNED,
            abi.signed_to_payload(lambdas),
            0,
        )
        if self._task9_push_graph(word) < 0:
            return -1
        word = self._make_word(
            abi.MOP_INT,
            abi.DATA_SIGNED,
            abi.signed_to_payload(descriptor_mode),
            0,
        )
        if self._task9_push_graph(word) < 0:
            return -1
        primitive = self._make_word(
            abi.MOP_PRIM_0,
            abi.DATA_LITERAL_ID,
            self.equal_star_literal_id,
            1,
        )
        if self._task9_push_graph(primitive) < 0:
            return -1
        return root

    def _task9_start_children(self, mode: int, count: int) -> None:
        if count <= 0 or count > len(self._task_eq_left_items):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        join_address = self._task_eq_join
        if (
            join_address < 0
            or join_address >= len(self._task_memory)
            or self._task_memory[join_address] == 0
            or self._opcode(self._task_memory[join_address]) != abi.MOP_JOIN
        ):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        self._task_eq_build_word = self._task_memory[join_address]
        self._task_eq_mode = mode
        self._task_eq_child_count = count
        self._task_eq_build_child = 0
        self._task_argcnt = 0
        self._task_fsp = join_address - 1
        self._task4_phase = TASK4_EQUALITY_BUILD_TASK

    def _task9_build_child_task(self, index: int) -> int:
        if index < 0 or index >= self._task_eq_child_count:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return -1
        if self._task_eq_mode == 1:
            source = self._task_eq_left_count - 1 - index
            if source < 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return -1
            left = self._task_eq_left_items[source]
            right = self._task_eq_right_items[source]
            lambdas = self._task_eq_lambdas + 1
            descriptor = 1
        elif self._task_eq_mode == 2:
            if index == 0:
                left = self._task_eq_left
                right = self._task_eq_right
                descriptor = 0
            else:
                source = self._task_eq_left_count - index
                if source < 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return -1
                left = self._task_eq_left_items[source]
                right = self._task_eq_right_items[source]
                descriptor = 1
            lambdas = self._task_eq_lambdas
        elif self._task_eq_mode == 3:
            left = self._task_eq_left
            right = self._task_eq_right
            lambdas = self._task_eq_lambdas
            descriptor = 0
        else:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return -1
        return self._task9_append_task_graph(left, right, lambdas, descriptor)

    def _task9_finish_child_result(self, result: int) -> None:
        join_address = self._task_eq_join
        if join_address < 0 or join_address >= len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        self._task_fsp = join_address
        self._task_argcnt = 0
        literal_id = self.equal_stuck_literal_id
        if result == 1:
            literal_id = self.true_literal_id
        elif result == 2:
            literal_id = self.false_literal_id
        elif result != 3:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if literal_id <= 0:
            self._fault(abi.FAULT_UNSUPPORTED_VALUE)
            return
        answer = self._make_word(
            abi.MOP_SYM,
            abi.DATA_LITERAL_ID,
            literal_id,
            1,
        )
        if not self._task4_task_push_result(answer):
            return
        self._task_pc = join_address
        self._task_direction = abi.DIRECTION_REVERSE
        self.microstate = MICRO_COMMIT

    def _task9_finish_equality(self, result: int) -> None:
        if not self._task9_pop_equality_frame():
            return
        result_pc = self._task_parent_address
        live_fsp = self._task_result_address
        restored = self._task4_pop_saved_quantum()
        if restored is None:
            return
        self._task_q = restored
        if result == 3:
            self._task_fsp = live_fsp
        elif result in (1, 2):
            literal_id = self.true_literal_id if result == 1 else self.false_literal_id
            if literal_id <= 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            self._task_memory[result_pc] = self._make_word(
                abi.MOP_SYM,
                abi.DATA_LITERAL_ID,
                literal_id,
                1,
            )
            self._task_fsp = result_pc
        else:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        self._task_pc = result_pc - 1
        self.microstate = MICRO_COMMIT

    def _task9_equality_clock(self) -> None:
        phase = self._task4_phase
        if phase == TASK4_EQUALITY_FIRE:
            self._task_prim_id = 0
            self._task_fire = 0
            if self._task_q <= 0:
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            right_address = self._task_pc
            left_address = right_address + 1
            if (
                right_address < 0
                or left_address >= len(self._task_memory)
                or self._task_memory[right_address] == 0
                or self._task_memory[left_address] == 0
            ):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            right = self._task_memory[right_address]
            left = self._task_memory[left_address]
            left_class = self._task9_constant_class(left)
            right_class = self._task9_constant_class(right)
            if left_class != 0 and right_class != 0:
                answer = self._bool_word(self._task9_constants_equal(left, right))
                if answer is None:
                    return
                self._task_memory[right_address] = answer
                self._task_fsp = right_address
                self._task_q -= 1
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            self._task_q -= 1
            if not self._task4_push_saved_quantum(self._task_q):
                return
            live_fsp = self._task_fsp
            if not self._task9_push_equality_frame(right_address, live_fsp):
                return
            task_root = self._task9_append_task_graph(
                left_address,
                right_address,
                0,
                1,
            )
            if task_root < 0:
                return
            parent = self._task9_push_graph(
                self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(task_root),
                    0,
                )
            )
            if parent < 0:
                return
            if self.equality_continue_literal_id <= 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            self._task_prim_id = self.equality_continue_literal_id
            self._task_fire = 1
            if not self._task4_enter_subgraph(self._task_env, task_root, parent):
                return
            self.microstate = MICRO_COMMIT
            return

        if phase == TASK4_EQUALITY_CHILD_INIT:
            primitive_pc = self._task_pc
            task_root = primitive_pc - 4
            if task_root < 0 or primitive_pc >= len(self._task_memory):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_argcnt != 4:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            left_word = self._task_memory[task_root]
            right_word = self._task_memory[task_root + 1]
            lambdas_word = self._task_memory[task_root + 2]
            descriptor_word = self._task_memory[task_root + 3]
            if (
                left_word == 0
                or right_word == 0
                or lambdas_word == 0
                or descriptor_word == 0
                or self._opcode(left_word) != abi.MOP_INT
                or self._opcode(right_word) != abi.MOP_INT
                or self._opcode(lambdas_word) != abi.MOP_INT
                or self._opcode(descriptor_word) != abi.MOP_INT
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            left = self._signed_data(left_word)
            right = self._signed_data(right_word)
            lambdas = self._signed_data(lambdas_word)
            descriptor = self._signed_data(descriptor_word)
            if (
                left is None
                or right is None
                or lambdas is None
                or descriptor is None
                or left < 0
                or right < 0
                or lambdas < 0
                or descriptor not in (0, 1)
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            join_address = self._task_fsp - 4
            if (
                join_address < 0
                or join_address >= len(self._task_memory)
                or self._task_memory[join_address] == 0
                or self._opcode(self._task_memory[join_address]) != abi.MOP_JOIN
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_eq_left = left
            self._task_eq_right = right
            self._task_eq_lambdas = lambdas
            self._task_eq_descriptor = descriptor
            self._task_eq_join = join_address
            self._task4_phase = TASK4_EQUALITY_DECOMPOSE
            return

        if phase == TASK4_EQUALITY_DECOMPOSE:
            left = self._task_eq_left
            right = self._task_eq_right
            if (
                left < 0
                or right < 0
                or left >= len(self._task_memory)
                or right >= len(self._task_memory)
            ):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            left_word = self._task_memory[left]
            right_word = self._task_memory[right]
            if left_word == 0 or right_word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task_eq_descriptor:
                if self._opcode(left_word) == abi.MOP_APP:
                    target = self._signed_data(left_word)
                    if target is None or target < 0 or target >= len(self._task_memory):
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    left = target
                    left_word = self._task_memory[target]
                    if left_word == 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                elif self._opcode(left_word) == abi.MOP_APP_VAR:
                    index = self._signed_data(left_word)
                    if index is None or index < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    left_word = self._make_word(
                        abi.MOP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(index),
                        1,
                    )
                if self._opcode(right_word) == abi.MOP_APP:
                    target = self._signed_data(right_word)
                    if target is None or target < 0 or target >= len(self._task_memory):
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    right = target
                    right_word = self._task_memory[target]
                    if right_word == 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                elif self._opcode(right_word) == abi.MOP_APP_VAR:
                    index = self._signed_data(right_word)
                    if index is None or index < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    right_word = self._make_word(
                        abi.MOP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(index),
                        1,
                    )
            self._task_eq_left = left
            self._task_eq_right = right
            self._task_eq_left_word = left_word
            self._task_eq_right_word = right_word
            left_opcode = self._opcode(left_word)
            right_opcode = self._opcode(right_word)
            if left_opcode == abi.MOP_UBV or right_opcode == abi.MOP_UBV:
                if (
                    left_opcode == abi.MOP_UBV
                    and right_opcode == abi.MOP_UBV
                    and self._signed_data(left_word) == self._signed_data(right_word)
                ):
                    self._task9_finish_child_result(1)
                else:
                    self._task9_finish_child_result(3)
                return
            left_class = self._task9_constant_class(left_word)
            right_class = self._task9_constant_class(right_word)
            if left_class != 0 or right_class != 0:
                if left_class == 0 or right_class == 0:
                    self._task9_finish_child_result(2)
                else:
                    self._task9_finish_child_result(
                        1 if self._task9_constants_equal(left_word, right_word) else 2
                    )
                return
            if left_opcode == abi.MOP_VAR or right_opcode == abi.MOP_VAR:
                variable_word = left_word if left_opcode == abi.MOP_VAR else right_word
                variable_index = self._signed_data(variable_word)
                if variable_index is None or variable_index < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if left_opcode != abi.MOP_VAR or right_opcode != abi.MOP_VAR:
                    self._task9_finish_child_result(
                        2 if variable_index < self._task_eq_lambdas else 3
                    )
                    return
                left_index = self._signed_data(left_word)
                right_index = self._signed_data(right_word)
                if left_index is None or right_index is None or left_index < 0 or right_index < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if left_index == right_index:
                    self._task9_finish_child_result(1)
                elif (
                    left_index < self._task_eq_lambdas
                    or right_index < self._task_eq_lambdas
                ):
                    self._task9_finish_child_result(2)
                else:
                    self._task9_finish_child_result(3)
                return
            if left_opcode == abi.MOP_CLOSURE or right_opcode == abi.MOP_CLOSURE:
                if left_opcode != abi.MOP_CLOSURE or right_opcode != abi.MOP_CLOSURE:
                    self._task9_finish_child_result(2)
                    return
                if left + 1 >= len(self._task_memory) or right + 1 >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                left_code = self._task_memory[left + 1]
                right_code = self._task_memory[right + 1]
                if (
                    left_code == 0
                    or right_code == 0
                    or self._opcode(left_code) != abi.MOP_NONE
                    or self._opcode(right_code) != abi.MOP_NONE
                ):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task9_finish_child_result(
                    1
                    if self._signed_data(left_word) == self._signed_data(right_word)
                    and self._signed_data(left_code) == self._signed_data(right_code)
                    else 2
                )
                return
            left_struct = (
                left_opcode == abi.MOP_STRUCT
                and self._data_kind(left_word) == abi.DATA_LITERAL_ID
            )
            right_struct = (
                right_opcode == abi.MOP_STRUCT
                and self._data_kind(right_word) == abi.DATA_LITERAL_ID
            )
            if left_struct or right_struct:
                if not left_struct or not right_struct:
                    self._task9_finish_child_result(2)
                    return
                if self._payload(left_word) != self._payload(right_word):
                    self._task9_finish_child_result(2)
                    return
                self._task_eq_left_count = 0
                self._task_eq_right_count = 0
                self._task_eq_cursor = left + 1
                self._task4_phase = TASK4_EQUALITY_STRUCT_LEFT
                return
            if left_opcode == abi.MOP_LAMBDA or right_opcode == abi.MOP_LAMBDA:
                if left_opcode != abi.MOP_LAMBDA or right_opcode != abi.MOP_LAMBDA:
                    self._task9_finish_child_result(2)
                    return
                self._task4_phase = TASK4_EQUALITY_LAMBDA
                return
            left_application = self._task4_is_app_prefix(left_word)
            right_application = self._task4_is_app_prefix(right_word)
            if left_application or right_application:
                if not left_application or not right_application:
                    self._task9_finish_child_result(2)
                    return
                self._task_eq_left_count = 0
                self._task_eq_right_count = 0
                self._task_eq_cursor = left
                self._task4_phase = TASK4_EQUALITY_APP_LEFT
                return
            if left_opcode == abi.MOP_CLOSURE or right_opcode == abi.MOP_CLOSURE:
                if left_opcode != abi.MOP_CLOSURE or right_opcode != abi.MOP_CLOSURE:
                    self._task9_finish_child_result(2)
                    return
                if left + 1 >= len(self._task_memory) or right + 1 >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                left_code = self._task_memory[left + 1]
                right_code = self._task_memory[right + 1]
                if (
                    left_code == 0
                    or right_code == 0
                    or self._opcode(left_code) != abi.MOP_NONE
                    or self._opcode(right_code) != abi.MOP_NONE
                ):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task9_finish_child_result(
                    1
                    if self._signed_data(left_word) == self._signed_data(right_word)
                    and self._signed_data(left_code) == self._signed_data(right_code)
                    else 2
                )
                return
            if left_opcode == abi.MOP_EP or right_opcode == abi.MOP_EP:
                if (
                    left_opcode == abi.MOP_EP
                    and right_opcode == abi.MOP_EP
                    and self._signed_data(left_word) == self._signed_data(right_word)
                ):
                    self._task9_finish_child_result(1)
                else:
                    self._task9_finish_child_result(3)
                return
            if left_opcode != right_opcode:
                self._task9_finish_child_result(2)
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if phase == TASK4_EQUALITY_STRUCT_LEFT:
            cursor = self._task_eq_cursor
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if (
                opcode in (abi.MOP_APP, abi.MOP_APP_VAR, abi.MOP_EP)
                or (not self._head(word) and self._task4_is_inline(word))
            ):
                if self._task_eq_left_count >= len(self._task_eq_left_items):
                    self._fault(abi.FAULT_CONTROL_OVERFLOW)
                    return
                self._task_eq_left_items[self._task_eq_left_count] = cursor
                self._task_eq_left_count += 1
                self._task_eq_cursor = cursor + 1
                return
            index = self._signed_data(word)
            if opcode != abi.MOP_VAR or index != 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_eq_cursor = self._task_eq_right + 1
            self._task4_phase = TASK4_EQUALITY_STRUCT_RIGHT
            return

        if phase == TASK4_EQUALITY_STRUCT_RIGHT:
            cursor = self._task_eq_cursor
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if (
                opcode in (abi.MOP_APP, abi.MOP_APP_VAR, abi.MOP_EP)
                or (not self._head(word) and self._task4_is_inline(word))
            ):
                if self._task_eq_right_count >= len(self._task_eq_right_items):
                    self._fault(abi.FAULT_CONTROL_OVERFLOW)
                    return
                self._task_eq_right_items[self._task_eq_right_count] = cursor
                self._task_eq_right_count += 1
                self._task_eq_cursor = cursor + 1
                return
            index = self._signed_data(word)
            if opcode != abi.MOP_VAR or index != 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_eq_left_count != self._task_eq_right_count:
                self._task9_finish_child_result(2)
                return
            if self._task_eq_left_count == 0:
                self._task9_finish_child_result(1)
                return
            self._task9_start_children(1, self._task_eq_left_count)
            return

        if phase == TASK4_EQUALITY_LAMBDA:
            left = self._task_eq_left
            right = self._task_eq_right
            if (
                left < 0
                or right < 0
                or left >= len(self._task_memory)
                or right >= len(self._task_memory)
            ):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            left_word = self._task_memory[left]
            right_word = self._task_memory[right]
            if left_word == 0 or right_word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            left_lambda = self._opcode(left_word) == abi.MOP_LAMBDA
            right_lambda = self._opcode(right_word) == abi.MOP_LAMBDA
            if left_lambda and right_lambda:
                self._task_eq_left = left + 1
                self._task_eq_right = right + 1
                self._task_eq_lambdas += 1
                return
            if left_lambda or right_lambda:
                self._task9_finish_child_result(2)
                return
            self._task9_start_children(3, 1)
            return

        if phase == TASK4_EQUALITY_APP_LEFT:
            cursor = self._task_eq_cursor
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task4_is_app_prefix(word):
                if self._task_eq_left_count >= len(self._task_eq_left_items):
                    self._fault(abi.FAULT_CONTROL_OVERFLOW)
                    return
                self._task_eq_left_items[self._task_eq_left_count] = cursor
                self._task_eq_left_count += 1
                self._task_eq_cursor = cursor + 1
                return
            self._task_eq_left = cursor
            self._task_eq_cursor = self._task_eq_right
            self._task4_phase = TASK4_EQUALITY_APP_RIGHT
            return

        if phase == TASK4_EQUALITY_APP_RIGHT:
            cursor = self._task_eq_cursor
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task4_is_app_prefix(word):
                if self._task_eq_right_count >= len(self._task_eq_right_items):
                    self._fault(abi.FAULT_CONTROL_OVERFLOW)
                    return
                self._task_eq_right_items[self._task_eq_right_count] = cursor
                self._task_eq_right_count += 1
                self._task_eq_cursor = cursor + 1
                return
            self._task_eq_right = cursor
            if self._task_eq_left_count != self._task_eq_right_count:
                self._task9_finish_child_result(2)
                return
            self._task9_start_children(2, self._task_eq_left_count + 1)
            return

        if phase == TASK4_EQUALITY_BUILD_TASK:
            child = self._task_eq_build_child
            if child < self._task_eq_child_count:
                root = self._task9_build_child_task(child)
                if root < 0:
                    return
                self._task_eq_child_root[child] = root
                self._task_eq_build_child = child + 1
                return
            self._task4_phase = TASK4_EQUALITY_BUILD_TRUE
            return

        if phase == TASK4_EQUALITY_BUILD_TRUE:
            if self.true_literal_id <= 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            root = self._task9_push_graph(
                self._make_word(
                    abi.MOP_SYM,
                    abi.DATA_LITERAL_ID,
                    self.true_literal_id,
                    1,
                )
            )
            if root < 0:
                return
            self._task_eq_true_root = root
            self._task_eq_branch_root = root
            self._task4_phase = TASK4_EQUALITY_BUILD_FALSE
            return

        if phase == TASK4_EQUALITY_BUILD_FALSE:
            if self.false_literal_id <= 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            root = self._task9_push_graph(
                self._make_word(
                    abi.MOP_SYM,
                    abi.DATA_LITERAL_ID,
                    self.false_literal_id,
                    1,
                )
            )
            if root < 0:
                return
            self._task_eq_false_root = root
            self._task_eq_build_child = self._task_eq_child_count - 1
            self._task4_phase = TASK4_EQUALITY_BUILD_IF
            return

        if phase == TASK4_EQUALITY_BUILD_IF:
            child = self._task_eq_build_child
            if child < 0:
                self._task4_phase = TASK4_EQUALITY_BUILD_JOIN
                return
            root = self._task_fsp + 1
            if self._task9_push_graph(
                self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_eq_false_root),
                    0,
                )
            ) < 0:
                return
            if self._task9_push_graph(
                self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_eq_branch_root),
                    0,
                )
            ) < 0:
                return
            if self._task9_push_graph(
                self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(self._task_eq_child_root[child]),
                    0,
                )
            ) < 0:
                return
            if self.equal_if_literal_id <= 0:
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            if self._task9_push_graph(
                self._make_word(
                    abi.MOP_PRIM_0,
                    abi.DATA_LITERAL_ID,
                    self.equal_if_literal_id,
                    1,
                )
            ) < 0:
                return
            self._task_eq_branch_root = root
            self._task_eq_build_child = child - 1
            return

        if phase == TASK4_EQUALITY_BUILD_JOIN:
            if self._task9_push_graph(self._task_eq_build_word) < 0:
                return
            self._task_pc = self._task_eq_branch_root
            self._task_direction = abi.DIRECTION_FORWARD
            self.microstate = MICRO_COMMIT
            return

        if phase == TASK4_EQUALITY_CONTINUE:
            self._task_prim_id = 0
            self._task_fire = 0
            if self._task_pc < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            child = self._task_memory[self._task_pc]
            if (
                child == 0
                or self._opcode(child) != abi.MOP_SYM
                or self._data_kind(child) != abi.DATA_LITERAL_ID
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            literal_id = self._payload(child)
            if literal_id == self.true_literal_id:
                self._task9_finish_equality(1)
            elif literal_id == self.false_literal_id:
                self._task9_finish_equality(2)
            elif literal_id == self.equal_stuck_literal_id:
                self._task9_finish_equality(3)
            else:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if phase == TASK4_EQUALITY_IF_FIRE:
            self._task_prim_id = 0
            self._task_fire = 0
            false_slot = self._task_pc - 2
            true_slot = self._task_pc - 1
            if false_slot < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            false_branch = self._task_memory[false_slot]
            true_branch = self._task_memory[true_slot]
            condition = self._task_memory[self._task_pc]
            if false_branch == 0 or true_branch == 0 or condition == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            true_path = -1
            if self._opcode(true_branch) in (abi.MOP_APP, abi.MOP_EP):
                path = self._task4_pop_control_path()
                if path is None:
                    return
                true_path = path
            false_path = -1
            if self._opcode(false_branch) in (abi.MOP_APP, abi.MOP_EP):
                path = self._task4_pop_control_path()
                if path is None:
                    return
                false_path = path
            if (
                self._opcode(condition) != abi.MOP_SYM
                or self._data_kind(condition) != abi.DATA_LITERAL_ID
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            condition_id = self._payload(condition)
            if condition_id == self.equal_stuck_literal_id:
                self._task_memory[false_slot] = self._make_word(
                    abi.MOP_SYM,
                    abi.DATA_LITERAL_ID,
                    self.equal_stuck_literal_id,
                    1,
                )
                self._task_fsp = false_slot
                self._task_pc = false_slot
                self.microstate = MICRO_COMMIT
                return
            if condition_id not in (self.true_literal_id, self.false_literal_id):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            selected_true = condition_id == self.true_literal_id
            selected = true_branch if selected_true else false_branch
            selected_path = true_path if selected_true else false_path
            selected_opcode = self._opcode(selected)
            if selected_opcode == abi.MOP_APP:
                target = self._signed_data(selected)
                if target is None or target < 0 or selected_path < 0:
                    self._fault(
                        abi.FAULT_INVALID_ADDRESS
                        if target is None or target < 0
                        else abi.FAULT_ILLEGAL_TRANSITION
                    )
                    return
                self._task_fsp = false_slot - 1
                self._task_env = selected_path
                self._task_pc = target
                self._task_direction = abi.DIRECTION_FORWARD
                self.microstate = MICRO_COMMIT
                return
            if selected_opcode == abi.MOP_EP:
                target = self._signed_data(selected)
                if target is None or target < 0 or selected_path < 0:
                    self._fault(
                        abi.FAULT_INVALID_ADDRESS
                        if target is None or target < 0
                        else abi.FAULT_ILLEGAL_TRANSITION
                    )
                    return
                self._task_env = selected_path
                self._task_if_target = target
                self._task_if_hops = 0
                self._task_if_false_slot = false_slot
                self._task4_kind = TASK4_IF
                self._task4_phase = TASK4_IF_EP_CHASE
                return
            self._task_memory[false_slot] = self._make_word(
                selected_opcode,
                self._data_kind(selected),
                self._payload(selected),
                1,
                self._definition_valid(selected),
                self._definition(selected),
            )
            self._task_fsp = false_slot
            self._task_pc = false_slot
            self.microstate = MICRO_COMMIT
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task10_reserve_slot(self) -> int | None:
        if self._task_mat_count >= len(self._task_mat_words):
            self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
            return None
        slot = self._task_mat_count
        self._task_mat_valid[slot] = 0
        self._task_mat_count += 1
        return slot

    def _task10_relinearize_clock(self, kind: int) -> None:
        sp = self._task_sp
        if kind == TASK10_LEAVE:
            expected = self._task_stack_a[sp]
            if self._task_mat_visit_count <= 0 or self._task_mat_visit_count - 1 != expected:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_mat_visit_count -= 1
            self._task_sp -= 1
            return

        if kind == TASK10_GRAPH:
            address = self._task_stack_a[sp]
            if address < 0 or address >= len(self._task_memory) or self._task_memory[address] == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            self._task_stack_kind[sp] = TASK10_VISIT_SCAN
            self._task_stack_e[sp] = 0
            return

        if kind == TASK10_VISIT_SCAN:
            address = self._task_stack_a[sp]
            head = self._task_stack_b[sp]
            visit_index = self._task_stack_e[sp]
            if visit_index < self._task_mat_visit_count:
                if (
                    self._task_mat_visit_address[visit_index] == address
                    and self._task_mat_visit_head[visit_index] == head
                ):
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_stack_e[sp] = visit_index + 1
                return
            if self._task_mat_visit_count >= len(self._task_mat_visit_address):
                self._fault(abi.FAULT_CONTROL_OVERFLOW)
                return
            active = self._task_mat_visit_count
            self._task_mat_visit_address[active] = address
            self._task_mat_visit_head[active] = head
            self._task_mat_visit_count += 1
            word = self._task_memory[address]
            opcode = self._opcode(word)
            self._task_sp -= 1
            if not self._task4_push(TASK10_LEAVE, active):
                return
            if self._task4_is_app_prefix(word):
                self._task4_push(TASK10_APP_SCAN, address, self._task_mat_count, 0)
                return
            if opcode == abi.MOP_RBLOCK:
                self._task4_push(
                    TASK10_RBLOCK_SCAN,
                    address,
                    self._task_mat_count,
                    0,
                    head,
                )
                return
            if opcode == abi.MOP_STRUCT:
                if not self._task4_mat_append(
                    self._make_word(
                        abi.MOP_STRUCT,
                        self._data_kind(word),
                        self._payload(word),
                        0,
                        self._definition_valid(word),
                        self._definition(word),
                    )
                ):
                    return
                self._task4_push(
                    TASK10_STRUCT_SCAN,
                    address + 1,
                    self._task_mat_count,
                    0,
                    head,
                )
                return
            if opcode == abi.MOP_LAMBDA:
                self._task4_push(TASK10_LAMBDA_SCAN, address, head)
                return
            if opcode in (
                abi.MOP_INT,
                abi.MOP_FLOAT,
                abi.MOP_CHAR,
                abi.MOP_SYM,
                abi.MOP_PRIM_0,
                abi.MOP_PRIM_1,
                abi.MOP_PRIM_2,
                abi.MOP_VAR,
            ):
                self._task4_mat_append(
                    self._make_word(
                        opcode,
                        self._data_kind(word),
                        self._payload(word),
                        head,
                        self._definition_valid(word),
                        self._definition(word),
                    )
                )
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK10_POINTER:
            address = self._task_stack_a[sp]
            if address < 0 or address >= self.working_memory_limit:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task_pub_root_state[address] == 2:
                self._task_pub_value = self._task_pub_root_result[address]
                self._task_sp -= 1
                return
            target = self._task_mat_count
            self._task_sp -= 1
            if not self._task4_push(TASK10_POINTER_DONE, address, target):
                return
            self._task4_push(TASK10_GRAPH, address, 1)
            return

        if kind == TASK10_POINTER_DONE:
            address = self._task_stack_a[sp]
            target = self._task_stack_b[sp]
            self._task_pub_root_state[address] = 2
            self._task_pub_root_result[address] = target
            self._task_pub_value = target
            self._task_sp -= 1
            return

        if kind == TASK10_APP_SCAN:
            cursor = self._task_stack_a[sp]
            slots = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            entry = self._task_memory[cursor]
            if entry == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task4_is_app_prefix(entry):
                if self._task10_reserve_slot() is None:
                    return
                self._task_stack_a[sp] = cursor + 1
                self._task_stack_c[sp] = count + 1
                return
            self._task_sp -= 1
            if not self._task4_push(TASK10_APP_PROCESS, cursor - count, slots, count, 0):
                return
            self._task4_push(TASK10_GRAPH, cursor, 1)
            return

        if kind == TASK10_APP_PROCESS:
            source_start = self._task_stack_a[sp]
            slots = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            index = self._task_stack_d[sp]
            if index >= count:
                self._task_sp -= 1
                return
            source = source_start + index
            slot = slots + index
            entry = self._task_memory[source]
            opcode = self._opcode(entry)
            if opcode == abi.MOP_APP_VAR:
                variable = self._signed_data(entry)
                if variable is None or variable < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(variable),
                    0,
                    self._definition_valid(entry),
                    self._definition(entry),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_d[sp] = index + 1
                return
            if opcode == abi.MOP_APP:
                target = self._signed_data(entry)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_stack_d[sp] = index + 1
                if not self._task4_push(TASK10_APP_POINTER_DONE, slot, source):
                    return
                self._task4_push(TASK10_POINTER, target)
                return
            if not self._head(entry) and self._task4_is_inline(entry):
                target = self._task_mat_count
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(target),
                    0,
                    self._definition_valid(entry),
                    self._definition(entry),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_d[sp] = index + 1
                self._task4_mat_append(
                    self._make_word(
                        opcode,
                        self._data_kind(entry),
                        self._payload(entry),
                        1,
                        self._definition_valid(entry),
                        self._definition(entry),
                    )
                )
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK10_APP_POINTER_DONE:
            slot = self._task_stack_a[sp]
            source = self._task_stack_b[sp]
            entry = self._task_memory[source]
            self._task_mat_words[slot] = self._make_word(
                abi.MOP_APP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_pub_value),
                0,
                self._definition_valid(entry),
                self._definition(entry),
            )
            self._task_mat_valid[slot] = 1
            self._task_sp -= 1
            return

        if kind == TASK10_STRUCT_SCAN:
            cursor = self._task_stack_a[sp]
            slots = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            head = self._task_stack_d[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor = self._task_memory[cursor]
            if descriptor == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(descriptor)
            if opcode == abi.MOP_VAR:
                variable = self._signed_data(descriptor)
                if variable != 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                if not self._task4_mat_append(
                    self._make_word(
                        abi.MOP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(0),
                        head,
                    )
                ):
                    return
                self._task_sp -= 1
                self._task4_push(TASK10_STRUCT_PROCESS, cursor - count, slots, count, 0)
                return
            if opcode == abi.MOP_APP or opcode == abi.MOP_APP_VAR or (
                not self._head(descriptor) and self._task4_is_inline(descriptor)
            ):
                if self._task10_reserve_slot() is None:
                    return
                self._task_stack_a[sp] = cursor + 1
                self._task_stack_c[sp] = count + 1
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK10_STRUCT_PROCESS:
            source_start = self._task_stack_a[sp]
            slots = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            index = self._task_stack_d[sp]
            if index >= count:
                self._task_sp -= 1
                return
            source = source_start + index
            slot = slots + index
            descriptor = self._task_memory[source]
            opcode = self._opcode(descriptor)
            if opcode == abi.MOP_APP_VAR:
                variable = self._signed_data(descriptor)
                if variable is None or variable < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP_VAR,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(variable),
                    0,
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_d[sp] = index + 1
                return
            if opcode == abi.MOP_APP:
                target = self._signed_data(descriptor)
                if target is None or target < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                self._task_stack_d[sp] = index + 1
                if not self._task4_push(TASK10_STRUCT_POINTER_DONE, slot, source):
                    return
                self._task4_push(TASK10_POINTER, target)
                return
            if not self._head(descriptor) and self._task4_is_inline(descriptor):
                target = self._task_mat_count
                self._task_mat_words[slot] = self._make_word(
                    abi.MOP_APP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(target),
                    0,
                    self._definition_valid(descriptor),
                    self._definition(descriptor),
                )
                self._task_mat_valid[slot] = 1
                self._task_stack_d[sp] = index + 1
                self._task4_mat_append(
                    self._make_word(
                        opcode,
                        self._data_kind(descriptor),
                        self._payload(descriptor),
                        1,
                        self._definition_valid(descriptor),
                        self._definition(descriptor),
                    )
                )
                return
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if kind == TASK10_STRUCT_POINTER_DONE:
            slot = self._task_stack_a[sp]
            source = self._task_stack_b[sp]
            descriptor = self._task_memory[source]
            self._task_mat_words[slot] = self._make_word(
                abi.MOP_APP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_pub_value),
                0,
                self._definition_valid(descriptor),
                self._definition(descriptor),
            )
            self._task_mat_valid[slot] = 1
            self._task_sp -= 1
            return

        if kind == TASK10_LAMBDA_SCAN:
            cursor = self._task_stack_a[sp]
            head = self._task_stack_b[sp]
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word != 0 and self._opcode(word) == abi.MOP_LAMBDA:
                if not self._task4_mat_append(
                    self._make_word(
                        abi.MOP_LAMBDA,
                        self._data_kind(word),
                        self._payload(word),
                        0,
                        self._definition_valid(word),
                        self._definition(word),
                    )
                ):
                    return
                self._task_stack_a[sp] = cursor + 1
                return
            self._task_sp -= 1
            self._task4_push(TASK10_GRAPH, cursor, head)
            return

        if kind == TASK10_RBLOCK_SCAN:
            root = self._task_stack_a[sp]
            slots = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            head = self._task_stack_d[sp]
            cursor = root + count
            if cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(word) == abi.MOP_RBLOCK:
                if self._task10_reserve_slot() is None:
                    return
                self._task_stack_c[sp] = count + 1
                return
            rup_count = self._signed_data(word)
            if self._opcode(word) != abi.MOP_RUP or rup_count != count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if not self._task4_mat_append(
                self._make_word(
                    abi.MOP_RUP,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(count),
                    0,
                )
            ):
                return
            body = cursor + 1
            self._task_sp -= 1
            if not self._task4_push(TASK10_RBLOCK_PROCESS, root, slots, count, 0):
                return
            self._task4_push(TASK10_GRAPH, body, head)
            return

        if kind == TASK10_RBLOCK_PROCESS:
            source_start = self._task_stack_a[sp]
            slots = self._task_stack_b[sp]
            count = self._task_stack_c[sp]
            index = self._task_stack_d[sp]
            if index >= count:
                self._task_sp -= 1
                return
            block = self._task_memory[source_start + index]
            binding = self._signed_data(block)
            if (
                block == 0
                or self._opcode(block) != abi.MOP_RBLOCK
                or binding is None
                or binding < 0
                or binding >= self.working_memory_limit
            ):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            name = self._task_memory[binding]
            if (
                name == 0
                or self._opcode(name) != abi.MOP_SYM
                or self._data_kind(name) != abi.DATA_LITERAL_ID
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            binding_output = self._task_mat_count
            self._task_mat_words[slots + index] = self._make_word(
                abi.MOP_RBLOCK,
                abi.DATA_SIGNED,
                abi.signed_to_payload(binding_output),
                0,
                self._definition_valid(block),
                self._definition(block),
            )
            self._task_mat_valid[slots + index] = 1
            if not self._task4_mat_append(
                self._make_word(
                    abi.MOP_SYM,
                    self._data_kind(name),
                    self._payload(name),
                    0,
                    self._definition_valid(name),
                    self._definition(name),
                )
            ):
                return
            self._task_stack_d[sp] = index + 1
            self._task4_push(TASK10_GRAPH, binding + 1, 1)
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task10_quantum_clock(self) -> None:
        if self._task4_phase == TASK4_QUANTUM_INIT:
            if not self._task_halted or self._task_pending_host_op != abi.HOST_NONE:
                self._fault(abi.FAULT_INVALID_RESUME)
                return
            self._task_mat_count = 0
            self._task_mat_visit_count = 0
            self._task_sp = -1
            if not self._task4_push(TASK10_GRAPH, self._task_pc, 1):
                return
            self._task4_phase = TASK4_QUANTUM_MATERIALIZE
            return

        if self._task4_phase == TASK4_QUANTUM_MATERIALIZE:
            if self._task_sp >= 0:
                kind = self._task_stack_kind[self._task_sp]
                if kind < TASK10_GRAPH or kind > TASK10_RBLOCK_PROCESS:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task10_relinearize_clock(kind)
                return
            if self._task_mat_count <= 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_mat_count >= self.working_memory_limit:
                self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                return
            self._task_quantum_cursor = 0
            self._task4_phase = TASK4_QUANTUM_CLEAR_MEMORY
            return

        if self._task4_phase == TASK4_QUANTUM_CLEAR_MEMORY:
            index = self._task_quantum_cursor
            if index < self.working_memory_limit:
                self._task_memory[index] = 0
                self._task_quantum_cursor = index + 1
                return
            self._task_quantum_write_index = 0
            self._task4_phase = TASK4_QUANTUM_WRITE_MEMORY
            return

        if self._task4_phase == TASK4_QUANTUM_WRITE_MEMORY:
            index = self._task_quantum_write_index
            if index < self._task_mat_count:
                if not self._task_mat_valid[index]:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task_memory[index] = self._task_mat_words[index]
                self._task_quantum_write_index = index + 1
                return
            self._task_memory[self._task_mat_count] = self._make_word(
                abi.MOP_STOP, abi.DATA_NONE, 0, 0
            )
            self._task_quantum_cursor = 0
            self._task4_phase = TASK4_QUANTUM_CLEAR_CONTROL
            return

        if self._task4_phase == TASK4_QUANTUM_CLEAR_CONTROL:
            index = self._task_quantum_cursor
            if index < len(self._task_control):
                self._task_control[index] = 0
                self._task_quantum_cursor = index + 1
                return
            self._task4_phase = TASK4_QUANTUM_FINISH
            return

        if self._task4_phase == TASK4_QUANTUM_FINISH:
            stop_address = self._task_mat_count
            self._task_pc = 0
            self._task_fsp = stop_address
            self._task_env = self.working_memory_limit
            self._task_c = -1
            self._task_direction = abi.DIRECTION_FORWARD
            self._task_q = self._task_quantum_value
            self._task_phi = 0
            self._task_free_space = self.working_memory_limit
            self._task_argcnt = 0
            self._task_prim_id = 0
            self._task_fire = 0
            self._task_s_a = 0
            self._task_s_a_valid = 0
            self._task_s_d = 0
            self._task_s_d_valid = 0
            self._task_halted = 0
            self._task_pending_host_op = abi.HOST_NONE
            self._task_pending_host_argument = 0
            self.microstate = MICRO_COMMIT
            return

        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _task11_io_clock(self) -> None:
        if self._task4_phase != TASK4_IO_FIRE:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        primitive_id = self._task_prim_id
        role = self._prim0_role(primitive_id)
        self._task_prim_id = 0
        self._task_fire = 0
        if self._task_q <= 0:
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if role == PRIM0_ROLE_IO_RETURN:
            if not 0 <= self._task_pc < len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            value = self._task_memory[self._task_pc]
            if value == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(value)
            if opcode not in (abi.MOP_INT, abi.MOP_FLOAT, abi.MOP_CHAR, abi.MOP_SYM):
                self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                return
            self._task_memory[self._task_pc] = self._clone_word(value, head=1)
            self._task_fsp = self._task_pc
            self._task_q -= 1
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if role not in (PRIM0_ROLE_IO_BIND, PRIM0_ROLE_IO_THEN):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        value_slot = self._task_pc
        continuation_slot = value_slot - 1
        if not 0 <= continuation_slot < len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        continuation = self._task_memory[continuation_slot]
        if continuation == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        if self._opcode(continuation) != abi.MOP_APP:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        continuation_target = self._signed_data(continuation)
        if continuation_target is None or continuation_target < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        continuation_path = self._task4_pop_control_path()
        if continuation_path is None:
            return

        self._task_q -= 1
        if role == PRIM0_ROLE_IO_THEN:
            self._task_fsp = continuation_slot - 1
            self._task_argcnt = 0
            self._task_env = continuation_path
            self._task_pc = continuation_target
            self._task_direction = abi.DIRECTION_FORWARD
            self.microstate = MICRO_COMMIT
            return

        if not 0 <= value_slot < len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        value = self._task_memory[value_slot]
        if value == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        value_opcode = self._opcode(value)
        supported = (
            value_opcode in (abi.MOP_INT, abi.MOP_FLOAT, abi.MOP_CHAR)
            or (value_opcode == abi.MOP_SYM and not self._definition_valid(value))
            or (value_opcode == abi.MOP_EP and self._signed_data(value) is not None)
        )
        if not supported:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        value_path = self._task_env
        self._task_fsp = continuation_slot - 1
        self._task_argcnt = 0
        if not self._task4_task_push_result(self._clone_word(value, head=0)):
            return
        if value_opcode == abi.MOP_EP and not self._task4_push_control_path(value_path):
            return
        self._task_env = continuation_path
        self._task_pc = continuation_target
        self._task_direction = abi.DIRECTION_FORWARD
        self.microstate = MICRO_COMMIT

    def _task4_clock(self) -> None:
        if not self._task4_active:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if self._task4_phase == TASK4_COPY_MEMORY or self._task4_phase == TASK4_COPY_CONTROL:
            self._task4_copy_clock()
            return
        if self._task4_kind == TASK4_JOIN:
            self._task4_join_clock()
            return
        if self._task4_kind == TASK4_VAR:
            self._task4_var_clock()
            return
        if self._task4_kind == TASK4_APP_VAR:
            self._task4_app_var_clock()
            return
        if self._task4_kind == TASK4_EP:
            self._task4_ep_clock()
            return
        if self._task4_kind == TASK4_IF:
            self._task4_if_clock()
            return
        if self._task4_kind == TASK4_RBLOCK:
            self._task8_rblock_clock()
            return
        if self._task4_kind == TASK4_RUP:
            self._task8_rup_clock()
            return
        if self._task4_kind == TASK4_RECP:
            if self._task4_phase >= TASK4_RECP_RECON_SCAN:
                self._task8_reconstruct_clock()
            else:
                self._task8_recp_clock()
            return
        if self._task4_kind == TASK4_STRUCT:
            self._task8_struct_clock()
            return
        if self._task4_kind == TASK4_EQUALITY:
            self._task9_equality_clock()
            return
        if self._task4_kind == TASK4_QUANTUM:
            self._task10_quantum_clock()
            return
        if self._task4_kind == TASK4_IO:
            self._task11_io_clock()
            return
        self._fault(abi.FAULT_ILLEGAL_TRANSITION)

    def _execute_join(self, word: int) -> None:
        self._task4_begin(TASK4_JOIN, TASK4_JOIN_INIT)
        self.microstate = MICRO_TASK4

    def _execute_lambda(self, word: int) -> None:
        if self.direction == abi.DIRECTION_REVERSE:
            self.phi -= 1
            if self.phi < 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self.pc -= 1
            return
        if not 0 <= self.fsp < len(self.memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        result_head = self.memory[self.fsp]
        if result_head == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        result_opcode = self._opcode(result_head)
        if self.q == 0 or self.argcnt == 0 or result_opcode == abi.MOP_STOP:
            if not self._push_result(word):
                return
            self.argcnt = 0
            self.phi += 1
            ubv = self._make_word(
                abi.MOP_UBV, abi.DATA_SIGNED, abi.signed_to_payload(self.phi), 0
            )
            if not self._allocate_environment(ubv):
                return
            self.pc += 1
            return
        if result_opcode == abi.MOP_APP_VAR:
            index = self._signed_data(result_head)
            if index is None or index < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            ubv = self._make_word(
                abi.MOP_UBV,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self.phi - index),
                0,
            )
            if not self._allocate_environment(ubv):
                return
        elif result_opcode == abi.MOP_EP:
            target = self._signed_data(result_head)
            if target is None or target < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._pop_control_path() is None:
                return
            binding = self._make_word(
                abi.MOP_EP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(target),
                0,
            )
            if not self._allocate_environment(binding):
                return
        elif result_opcode == abi.MOP_APP:
            target = self._signed_data(result_head)
            if target is None or target < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            saved_path = self._pop_control_path()
            if saved_path is None:
                return
            pointer = self._make_word(
                abi.MOP_NONE,
                abi.DATA_SIGNED,
                abi.signed_to_payload(target),
                0,
            )
            closure = self._make_word(
                abi.MOP_CLOSURE,
                abi.DATA_SIGNED,
                abi.signed_to_payload(saved_path),
                0,
            )
            fault, _, env, free_space = abi.red2_allocate_environment_block(
                self.memory,
                self.fsp,
                self.env,
                self.free_space,
                [closure, pointer],
            )
            if fault != abi.FAULT_NONE:
                self._fault(fault)
                return
            self.env = env
            self.free_space = free_space
        else:
            if not self._allocate_environment(self._clone_word(result_head, 0)):
                return
        self.q -= 1
        self.fsp -= 1
        self.argcnt -= 1
        self.pc += 1

    def _task8_struct_clock(self) -> None:
        if self._task4_phase == TASK4_STRUCT_SELECTOR_FIRE:
            primitive_id = self._task_prim_id
            if primitive_id == 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_prim_id = 0
            self._task_fire = 0

            if primitive_id == self.cons_literal_id:
                if self._task_q <= 0:
                    self._task_pc -= 1
                    self.microstate = MICRO_COMMIT
                    return
                base = self._task_pc
                if base < 0 or base + 3 >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                right = self._task_memory[base]
                left = self._task_memory[base + 1]
                if right == 0 or left == 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if self.pair_literal_id <= 0:
                    self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                    return
                old_fsp = self._task_fsp
                next_root = max(old_fsp + 1, base + 4)
                right_opcode = self._opcode(right)
                left_opcode = self._opcode(left)
                right_root = 0
                left_root = 0
                if right_opcode == abi.MOP_APP:
                    right_target = self._signed_data(right)
                    if right_target is None or right_target < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    right_field = self._make_word(
                        abi.MOP_APP, abi.DATA_SIGNED, abi.signed_to_payload(right_target), 0
                    )
                elif right_opcode == abi.MOP_APP_VAR:
                    right_index = self._signed_data(right)
                    if right_index is None or right_index < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    right_field = self._make_word(
                        abi.MOP_APP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(right_index + 1),
                        0,
                    )
                elif right_opcode == abi.MOP_NONE:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                else:
                    right_root = next_root
                    next_root += 1
                    right_field = self._make_word(
                        abi.MOP_APP, abi.DATA_SIGNED, abi.signed_to_payload(right_root), 0
                    )
                if left_opcode == abi.MOP_APP:
                    left_target = self._signed_data(left)
                    if left_target is None or left_target < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    left_field = self._make_word(
                        abi.MOP_APP, abi.DATA_SIGNED, abi.signed_to_payload(left_target), 0
                    )
                elif left_opcode == abi.MOP_APP_VAR:
                    left_index = self._signed_data(left)
                    if left_index is None or left_index < 0:
                        self._fault(abi.FAULT_INVALID_ADDRESS)
                        return
                    left_field = self._make_word(
                        abi.MOP_APP_VAR,
                        abi.DATA_SIGNED,
                        abi.signed_to_payload(left_index + 1),
                        0,
                    )
                elif left_opcode == abi.MOP_NONE:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                else:
                    left_root = next_root
                    next_root += 1
                    left_field = self._make_word(
                        abi.MOP_APP, abi.DATA_SIGNED, abi.signed_to_payload(left_root), 0
                    )
                last = max(old_fsp, base + 3, next_root - 1)
                if last >= self._task_free_space or last >= len(self._task_memory):
                    self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                    return
                self._task_memory[base] = self._make_word(
                    abi.MOP_STRUCT, abi.DATA_LITERAL_ID, self.pair_literal_id, 0
                )
                self._task_memory[base + 1] = right_field
                self._task_memory[base + 2] = left_field
                self._task_memory[base + 3] = self._make_word(
                    abi.MOP_VAR, abi.DATA_SIGNED, abi.signed_to_payload(0), 1
                )
                if right_root != 0:
                    self._task_memory[right_root] = self._make_word(
                        right_opcode,
                        self._data_kind(right),
                        self._payload(right),
                        1,
                        self._definition_valid(right),
                        self._definition(right),
                    )
                if left_root != 0:
                    self._task_memory[left_root] = self._make_word(
                        left_opcode,
                        self._data_kind(left),
                        self._payload(left),
                        1,
                        self._definition_valid(left),
                        self._definition(left),
                    )
                self._task_fsp = last
                self._task_q -= 1
                self._task_pc = base - 1
                self.microstate = MICRO_COMMIT
                return

            tag = self._struct_selector_tag(primitive_id)
            field_offset = self._struct_selector_offset(primitive_id)
            if tag == 0 or field_offset <= 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if self._task_q <= 0:
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            if self._task_pc < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            operand = self._task_memory[self._task_pc]
            if operand == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(operand) != abi.MOP_APP:
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            root_address = self._signed_data(operand)
            if root_address is None or root_address < 0 or root_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            root = self._task_memory[root_address]
            if root == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if (
                self._opcode(root) != abi.MOP_STRUCT
                or self._data_kind(root) != abi.DATA_LITERAL_ID
                or self._payload(root) != tag
            ):
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            descriptor_address = root_address + field_offset
            if descriptor_address < 0 or descriptor_address >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor = self._task_memory[descriptor_address]
            if descriptor == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            descriptor_opcode = self._opcode(descriptor)
            if descriptor_opcode == abi.MOP_APP:
                source_address = self._signed_data(descriptor)
                if source_address is None or source_address < 0 or source_address >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                value = self._task_memory[source_address]
                if value == 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
            elif descriptor_opcode == abi.MOP_APP_VAR:
                self._task_pc -= 1
                self.microstate = MICRO_COMMIT
                return
            elif (
                self._head(descriptor) == 0
                and descriptor_opcode in (
                    abi.MOP_EP,
                    abi.MOP_INT,
                    abi.MOP_FLOAT,
                    abi.MOP_CHAR,
                    abi.MOP_SYM,
                    abi.MOP_PRIM_0,
                    abi.MOP_PRIM_1,
                    abi.MOP_PRIM_2,
                )
            ):
                source_address = descriptor_address
                value = self._clone_word(descriptor, 1)
            else:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return

            value_opcode = self._opcode(value)
            reducible = (
                self._task4_is_app_prefix(value)
                or value_opcode == abi.MOP_LAMBDA
                or (value_opcode == abi.MOP_SYM and self._definition_valid(value) != 0)
            )
            if reducible:
                if self.struct_selector_result_literal_id <= 0:
                    self._fault(abi.FAULT_UNSUPPORTED_VALUE)
                    return
                self._task_q -= 1
                self._task_prim_id = self.struct_selector_result_literal_id
                self._task_fire = 1
                if not self._task4_enter_subgraph(
                    self._task_env, source_address, self._task_pc
                ):
                    return
                self.microstate = MICRO_COMMIT
                return
            if value_opcode == abi.MOP_STRUCT:
                self._task_struct_source = source_address
                self._task_struct_cursor = source_address + 1
                self._task_struct_destination = self._task_pc
                self._task_struct_old_fsp = self._task_fsp
                self._task_struct_write_index = 0
                self._task_struct_copy_backward = 0
                self._task_struct_copy_charge = 1
                self._task4_phase = TASK4_STRUCT_COPY_SCAN
                return
            self._task_memory[self._task_pc] = self._clone_word(value, 1)
            self._task_fsp = self._task_pc
            self._task_q -= 1
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase == TASK4_STRUCT_SELECTOR_RESULT:
            if self._task_prim_id != self.struct_selector_result_literal_id:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_prim_id = 0
            self._task_fire = 0
            if self._task_pc < 0 or self._task_pc >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            selected = self._task_memory[self._task_pc]
            if selected == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._opcode(selected) == abi.MOP_APP:
                source_address = self._signed_data(selected)
                if source_address is None or source_address < 0 or source_address >= len(self._task_memory):
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                root = self._task_memory[source_address]
                if root == 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                if self._opcode(root) == abi.MOP_STRUCT:
                    self._task_struct_source = source_address
                    self._task_struct_cursor = source_address + 1
                    self._task_struct_destination = self._task_pc
                    self._task_struct_old_fsp = self._task_fsp
                    self._task_struct_write_index = 0
                    self._task_struct_copy_backward = 0
                    self._task_struct_copy_charge = 0
                    self._task4_phase = TASK4_STRUCT_COPY_SCAN
                    return
                self._task_struct_source = source_address
                self._task_struct_destination = self._task_pc
                self._task_struct_source_is_lambda = int(self._opcode(root) == abi.MOP_LAMBDA)
                self._task_struct_write_index = 0
                self._task_mat_count = 0
                self._task_mat_visit_count = 0
                self._task_sp = -1
                self._task_quantum_cursor = 0
                self._task4_phase = TASK4_STRUCT_PROMOTE_CLEAR
                return
            self._task_memory[self._task_pc] = self._clone_word(selected, 1)
            self._task_fsp = self._task_pc
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase == TASK4_STRUCT_PROMOTE_CLEAR:
            index = self._task_quantum_cursor
            if index < len(self._task_pub_root_state):
                self._task_pub_root_state[index] = 0
                self._task_pub_root_result[index] = 0
                self._task_quantum_cursor = index + 1
                return
            self._task_quantum_cursor = 0
            if not self._task4_push(TASK10_GRAPH, self._task_struct_source, 1):
                return
            self._task4_phase = TASK4_STRUCT_PROMOTE_MATERIALIZE
            return

        if self._task4_phase == TASK4_STRUCT_PROMOTE_MATERIALIZE:
            if self._task_sp >= 0:
                kind = self._task_stack_kind[self._task_sp]
                if kind < TASK10_GRAPH or kind > TASK10_RBLOCK_PROCESS:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                self._task10_relinearize_clock(kind)
                return
            if self._task_mat_count <= 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            destination = self._task_struct_destination
            last = destination + self._task_mat_count - 1
            if destination < 0 or last >= self._task_free_space or last >= len(self._task_memory):
                self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                return
            self._task_struct_write_index = 0
            self._task4_phase = TASK4_STRUCT_PROMOTE_WRITE
            return

        if self._task4_phase == TASK4_STRUCT_PROMOTE_WRITE:
            index = self._task_struct_write_index
            if index < 0 or index >= self._task_mat_count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            if not self._task_mat_valid[index]:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            destination = self._task_struct_destination
            graph_word = self._task_mat_words[index]
            opcode = self._opcode(graph_word)
            if opcode == abi.MOP_APP or opcode == abi.MOP_RBLOCK:
                relative = self._signed_data(graph_word)
                if relative is None or relative < 0:
                    self._fault(abi.FAULT_INVALID_ADDRESS)
                    return
                graph_word = self._make_word(
                    opcode,
                    abi.DATA_SIGNED,
                    abi.signed_to_payload(destination + relative),
                    self._head(graph_word),
                    self._definition_valid(graph_word),
                    self._definition(graph_word),
                )
            self._task_memory[destination + index] = graph_word
            if index + 1 < self._task_mat_count:
                self._task_struct_write_index = index + 1
                return
            last = destination + self._task_mat_count - 1
            self._task_fsp = last
            if self._task_struct_source_is_lambda and self._task_argcnt > 0:
                self._task_fsp = self._task_pc - 1
                self._task_direction = abi.DIRECTION_FORWARD
                self.microstate = MICRO_COMMIT
                return
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase == TASK4_STRUCT_COPY_SCAN:
            source = self._task_struct_source
            cursor = self._task_struct_cursor
            if source < 0 or source >= len(self._task_memory) or cursor < 0 or cursor >= len(self._task_memory):
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            root = self._task_memory[source]
            if root == 0 or self._opcode(root) != abi.MOP_STRUCT:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            word = self._task_memory[cursor]
            if word == 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            opcode = self._opcode(word)
            if opcode == abi.MOP_VAR:
                index = self._signed_data(word)
                if index != 0:
                    self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                    return
                count = cursor - source + 1
                destination = self._task_struct_destination
                last = destination + count - 1
                if destination < 0 or last >= self._task_free_space or last >= len(self._task_memory):
                    self._fault(abi.FAULT_GRAPH_ENV_COLLISION)
                    return
                self._task_struct_copy_backward = int(
                    destination > source and destination <= cursor
                )
                self._task_struct_write_index = count - 1 if self._task_struct_copy_backward else 0
                self._task4_phase = TASK4_STRUCT_COPY_WRITE
                return
            if opcode not in (
                abi.MOP_APP,
                abi.MOP_APP_VAR,
                abi.MOP_EP,
                abi.MOP_INT,
                abi.MOP_FLOAT,
                abi.MOP_CHAR,
                abi.MOP_SYM,
                abi.MOP_PRIM_0,
                abi.MOP_PRIM_1,
                abi.MOP_PRIM_2,
            ):
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_struct_cursor = cursor + 1
            return

        if self._task4_phase == TASK4_STRUCT_COPY_WRITE:
            source = self._task_struct_source
            source_last = self._task_struct_cursor
            destination = self._task_struct_destination
            count = source_last - source + 1
            index = self._task_struct_write_index
            if index < 0 or index >= count:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_memory[destination + index] = self._task_memory[source + index]
            if self._task_struct_copy_backward:
                if index > 0:
                    self._task_struct_write_index = index - 1
                    return
            else:
                if index + 1 < count:
                    self._task_struct_write_index = index + 1
                    return
            last = destination + count - 1
            self._task_memory[last] = self._make_word(
                abi.MOP_VAR, abi.DATA_SIGNED, abi.signed_to_payload(0), 1
            )
            self._task_fsp = max(self._task_struct_old_fsp, last)
            if self._task_struct_copy_charge:
                self._task_q -= 1
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if self._task4_phase != TASK4_STRUCT_EXEC:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        if self._task_pc < 0 or self._task_pc >= len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        word = self._task_memory[self._task_pc]
        if (
            word == 0
            or self._opcode(word) != abi.MOP_STRUCT
            or self._data_kind(word) != abi.DATA_LITERAL_ID
            or self._payload(word) == 0
        ):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return

        if self._task_direction == abi.DIRECTION_REVERSE:
            restored = self._task4_pop_saved_quantum()
            if restored is None:
                return
            next_phi = self._task_phi - 1
            if next_phi < 0:
                self._fault(abi.FAULT_ILLEGAL_TRANSITION)
                return
            self._task_q = restored
            self._task_phi = next_phi
            self._task_pc -= 1
            self.microstate = MICRO_COMMIT
            return

        if self._task_fsp < 0 or self._task_fsp >= len(self._task_memory):
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        result_head = self._task_memory[self._task_fsp]
        if result_head == 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        result_opcode = self._opcode(result_head)
        if self._task_q == 0 or result_opcode not in (
            abi.MOP_APP,
            abi.MOP_APP_VAR,
            abi.MOP_EP,
        ):
            if not self._task4_push_saved_quantum(self._task_q):
                return
            self._task_q = 0
            if not self._task4_task_push_result(word):
                return
            self._task_argcnt = 0
            self._task_phi += 1
            ubv = self._make_word(
                abi.MOP_UBV,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_phi),
                0,
            )
            if not self._task8_allocate_environment_word(ubv):
                return
            self._task_pc += 1
            self.microstate = MICRO_COMMIT
            return

        if result_opcode == abi.MOP_APP_VAR:
            index = self._signed_data(result_head)
            if index is None or index < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            ubv = self._make_word(
                abi.MOP_UBV,
                abi.DATA_SIGNED,
                abi.signed_to_payload(self._task_phi - index),
                0,
            )
            if not self._task8_allocate_environment_word(ubv):
                return
        elif result_opcode == abi.MOP_EP:
            target = self._signed_data(result_head)
            if target is None or target < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            if self._task4_pop_control_path() is None:
                return
            binding = self._make_word(
                abi.MOP_EP,
                abi.DATA_SIGNED,
                abi.signed_to_payload(target),
                0,
            )
            if not self._task8_allocate_environment_word(binding):
                return
        else:
            target = self._signed_data(result_head)
            if target is None or target < 0:
                self._fault(abi.FAULT_INVALID_ADDRESS)
                return
            saved_path = self._task4_pop_control_path()
            if saved_path is None:
                return
            pointer = self._make_word(
                abi.MOP_NONE,
                abi.DATA_SIGNED,
                abi.signed_to_payload(target),
                0,
            )
            closure = self._make_word(
                abi.MOP_CLOSURE,
                abi.DATA_SIGNED,
                abi.signed_to_payload(saved_path),
                0,
            )
            fault, _, env, free_space = abi.red2_allocate_environment_block(
                self._task_memory,
                self._task_fsp,
                self._task_env,
                self._task_free_space,
                (closure, pointer),
            )
            if fault != abi.FAULT_NONE:
                self._fault(fault)
                return
            self._task_env = env
            self._task_free_space = free_space

        self._task_q -= 1
        self._task_fsp -= 1
        self._task_argcnt -= 1
        self._task_pc += 1
        self.microstate = MICRO_COMMIT

    def _execute_struct(self, word: int) -> None:
        if (
            self._data_kind(word) != abi.DATA_LITERAL_ID
            or self._payload(word) == 0
        ):
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        self._task4_begin(TASK4_STRUCT, TASK4_STRUCT_EXEC)
        self.microstate = MICRO_TASK4

    def _execute_ubv(self, word: int) -> None:
        if self.direction != abi.DIRECTION_FORWARD:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        binder_depth = self._signed_data(word)
        if binder_depth is None:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        result = self._make_word(
            abi.MOP_VAR,
            abi.DATA_SIGNED,
            abi.signed_to_payload(self.phi - binder_depth),
            1,
        )
        if not self._push_result(result):
            return
        self.pc = self.fsp - 1
        self.direction = abi.DIRECTION_REVERSE

    def _execute_var(self, word: int) -> None:
        if self.direction != abi.DIRECTION_FORWARD:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        index = self._signed_data(word)
        if index is None or index < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        self._task4_begin(TASK4_VAR, TASK4_VAR_LOOKUP)
        self._task_var_index = index
        self._task_var_address = self._task_env
        self._task_var_remaining = index
        self._task_var_hops = 0
        self._task_s_d = index
        self._task_s_d_valid = 1
        self.microstate = MICRO_TASK4

    def _execute_rblock(self, word: int) -> None:
        binding = self._signed_data(word)
        if binding is None or binding < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        self._task4_begin(TASK4_RBLOCK, TASK4_RBLOCK_EXEC)
        self.microstate = MICRO_TASK4

    def _execute_rup(self, word: int) -> None:
        count = self._signed_data(word)
        if count is None or count < 0:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        self._task4_begin(TASK4_RUP, TASK4_RUP_INIT)
        self.microstate = MICRO_TASK4

    def _execute_recp(self, word: int) -> None:
        address = self._signed_data(word)
        if address is None or address < 0:
            self._fault(abi.FAULT_INVALID_ADDRESS)
            return
        self._task4_begin(TASK4_RECP, TASK4_RECP_EXEC)
        self._task_rec_address = address
        self._task_rec_head = self._head(word)
        self.microstate = MICRO_TASK4

    def _execute_stop(self) -> None:
        if self.direction != abi.DIRECTION_REVERSE:
            self._fault(abi.FAULT_ILLEGAL_TRANSITION)
            return
        self._discard_completed_definition_paths()
        if self.fault != abi.FAULT_NONE:
            return
        self.pc += 1
        self.halted = 1
