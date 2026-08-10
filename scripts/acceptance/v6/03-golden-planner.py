#!/usr/bin/env python3
"""Gate 03: Golden planner — correct packages and dependencies."""
import sys
def main(log_dir):
    from infra_again.implementation import generate_implementation_plan
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN','requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi','metadata':{'name':'Customer API Service'}}
    plan = generate_implementation_plan(design)
    pkg_ids = {w.package_id for w in plan.work_packages}
    assert 'wp-sec-001' in pkg_ids
    assert any('APP' in w.package_id for w in plan.work_packages)
    assert any('DATA' in w.package_id for w in plan.work_packages)
    assert any('INT' in w.package_id for w in plan.work_packages)
    assert any('TEST' in w.package_id for w in plan.work_packages)
    assert any('DEP' in w.package_id for w in plan.work_packages)
    assert len(plan.dependencies) >= 5
    assert len(plan.critical_path) >= 4
    assert plan.critical_path_duration == ''
    plan.approve('qa')
    assert plan.status.value == 'APPROVED_FOR_EXECUTION'
    # Material change → invalidation
    old = plan.plan_checksum
    from infra_again.implementation.models import ImplementationTask, WorkPackageType
    plan.work_packages[0].tasks.append(ImplementationTask(task_id='NEW',work_package_id=plan.work_packages[0].package_id,title='X'))
    assert plan.check_changed_after_approval()
    print(f"PASS: {len(plan.work_packages)} pkgs, {len(plan.dependencies)} deps, critical={len(plan.critical_path)}, approved, invalidated")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
