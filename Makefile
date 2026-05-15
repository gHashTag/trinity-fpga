# Trinity FPGA — Root Makefile
# Wave-35 Lane W: LUT-NPU RTL targets
# Wave-36 Lane Y: AVS-48 RTL targets
# Wave-37 Lane AA: Sub-V_T RTL targets (OP_SUBTH_CLK=0xE4)
# R-SI-1: synth_check_no_star verifies zero star operators in RTL

# Wave-41 Lane HH: Sparse-Activation Gating (OP_SPARSE_SKIP=0xE8)
SPARSE_RTL = rtl/sparse_gate.sv
SPARSE_TB  = tb/sparse_gate_tb.sv

# RTL source
LUT_NPU_RTL = rtl/lut_npu/lut_npu_controller.sv
LUT_NPU_TB  = tb/lut_npu/lut_npu_controller_tb.sv

# AVS-48 RTL source (Wave-36 Lane Y)
AVS_RTL = rtl/avs/avs_regulator.sv
AVS_TB  = tb/avs/avs_regulator_tb.sv

# Sub-V_T RTL source (Wave-37 Lane AA)
SUBTH_RTL = rtl/subth/subth_clock_divider.sv
SUBTH_TB  = tb/subth/subth_clock_divider_tb.sv

.PHONY: synth_check_no_star sim_lut_npu synth_check_no_star_avs sim_avs synth_check_no_star_subth sim_subth synth_check_no_star_sparse sparse_tb help

# R-SI-1 compliance check: zero star operators in synthesizable RTL
synth_check_no_star:
	@count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(LUT_NPU_RTL) | grep -v "^\s*//" | wc -l); \
	 if [ $$count -ne 0 ]; then \
	   echo "FAIL: $$count star op(s) in $(LUT_NPU_RTL)"; \
	   grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(LUT_NPU_RTL) | grep -v "^\s*//"; \
	   exit 1; \
	 fi; \
	 echo "R-SI-1 OK: zero star operators in $(LUT_NPU_RTL)"

# iverilog simulation target
sim_lut_npu:
	iverilog -g2001 -o /tmp/tb_lut_npu.vvp $(LUT_NPU_RTL) $(LUT_NPU_TB) && vvp /tmp/tb_lut_npu.vvp

# R-SI-1 compliance check for AVS RTL
synth_check_no_star_avs:
	@count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(AVS_RTL) | grep -v "^\s*//" | wc -l); \
	 if [ $$count -ne 0 ]; then \
	   echo "FAIL: $$count star op(s) in $(AVS_RTL)"; \
	   grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(AVS_RTL) | grep -v "^\s*//"; \
	   exit 1; \
	 fi; \
	 echo "R-SI-1 OK: zero star operators in $(AVS_RTL)"

# iverilog simulation for AVS-48 (Wave-36 Lane Y)
sim_avs:
	iverilog -g2012 -o /tmp/tb_avs.vvp $(AVS_RTL) $(AVS_TB) && vvp /tmp/tb_avs.vvp

# R-SI-1 compliance check for Sub-V_T RTL (Wave-37 Lane AA)
synth_check_no_star_subth:
	@count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(SUBTH_RTL) | grep -v "^\s*//" | wc -l); \
	 if [ $$count -ne 0 ]; then \
	   echo "FAIL: $$count star op(s) in $(SUBTH_RTL)"; \
	   grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(SUBTH_RTL) | grep -v "^\s*//"; \
	   exit 1; \
	 fi; \
	 echo "R-SI-1 OK: zero star operators in $(SUBTH_RTL)"

# iverilog simulation for Sub-V_T clock divider (Wave-37 Lane AA)
sim_subth:
	iverilog -g2012 -o /tmp/tb_subth.vvp $(SUBTH_RTL) $(SUBTH_TB) && vvp /tmp/tb_subth.vvp

# R-SI-1 compliance check for Sparse-Gate RTL (Wave-41 Lane HH)
synth_check_no_star_sparse:
	@count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(SPARSE_RTL) | grep -v "^\s*//" | wc -l); \
	 if [ $$count -ne 0 ]; then \
	   echo "FAIL: $$count star op(s) in $(SPARSE_RTL)"; \
	   grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(SPARSE_RTL) | grep -v "^\s*//"; \
	   exit 1; \
	 fi; \
	 echo "R-SI-1 OK: zero star operators in $(SPARSE_RTL)"

# iverilog simulation for Sparse-Activation Gating (Wave-41 Lane HH)
sparse_tb: synth_check_no_star_sparse
	iverilog -g2012 -o /tmp/tb_sparse_gate.vvp $(SPARSE_RTL) $(SPARSE_TB) && \
	vvp /tmp/tb_sparse_gate.vvp | tee /tmp/sparse_tb.log && \
	grep -q 'ALL 10/10 PASS' /tmp/sparse_tb.log && echo '\nsparse_tb: 10/10 PASS ✓'

help:
	@echo "Wave-35 Lane W — LUT-NPU RTL targets:"
	@echo "  make synth_check_no_star      -- R-SI-1: verify zero star ops (LUT-NPU)"
	@echo "  make sim_lut_npu              -- run iverilog simulation (LUT-NPU)"
	@echo "Wave-36 Lane Y — AVS-48 RTL targets:"
	@echo "  make synth_check_no_star_avs  -- R-SI-1: verify zero star ops (AVS)"
	@echo "  make sim_avs                  -- run iverilog simulation (AVS-48)"
	@echo "Wave-37 Lane AA — Sub-V_T RTL targets:"
	@echo "  make synth_check_no_star_subth -- R-SI-1: verify zero star ops (Sub-V_T)"
	@echo "  make sim_subth                 -- run iverilog simulation (Sub-V_T)"
	@echo "Wave-41 Lane HH — Sparse-Activation Gating targets:"
	@echo "  make synth_check_no_star_sparse -- R-SI-1: verify zero star ops (Sparse-Gate)"
	@echo "  make sparse_tb                  -- run iverilog simulation 10/10 (Sparse-Gate)"

# Wave-42 Lane JJ: Stochastic Rounding (OP_STOCH_ROUND=0xE9)
STOCH_RTL  = rtl/lfsr32.sv rtl/stoch_round.sv
STOCH_TB   = tb/stoch_round_tb.sv

.PHONY: synth_check_no_star_stoch stoch_tb

# R-SI-1 compliance check for Stochastic-Round RTL (Wave-42 Lane JJ)
synth_check_no_star_stoch:
	@for f in $(STOCH_RTL); do \
	  count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $$f | grep -v "^\s*//" | wc -l); \
	  if [ $$count -ne 0 ]; then \
	    echo "FAIL: $$count star op(s) in $$f"; \
	    exit 1; \
	  fi; \
	done; \
	echo "R-SI-1 OK: zero star operators in stoch_round RTL"

# iverilog simulation for Stochastic-Round (Wave-42 Lane JJ)
stoch_tb: synth_check_no_star_stoch
	iverilog -g2012 -o /tmp/stoch_tb $(STOCH_RTL) $(STOCH_TB) && \
	vvp /tmp/stoch_tb | tee /tmp/stoch_tb.log && \
	grep -q 'ALL 10/10 PASS' /tmp/stoch_tb.log && echo '\nstoch_tb: 10/10 PASS ✓'
