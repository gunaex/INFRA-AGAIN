#!/usr/bin/env python3
"""Gate 05: Readiness, blockers, risks."""
import sys
def main(log_dir):
    from infra_again.implementation import generate_implementation_plan
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN','requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi','metadata':{'name':'Test'}}
    plan = generate_implementation_plan(design)
    assert plan.readiness.value == 'PARTIALLY_READY'
    assert len(plan.blockers) == 2
    assert len(plan.risks) == 2
    assert len(plan.gates) == 4
    assert len(plan.open_questions) >= 3
    print(f"PASS: readiness={plan.readiness.value}, blockers={len(plan.blockers)}, risks={len(plan.risks)}, gates={len(plan.gates)}, questions={len(plan.open_questions)}")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
