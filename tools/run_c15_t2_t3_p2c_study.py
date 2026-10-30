"""Offline, seeded T2/T3 P2C comparison. Run: PYTHONPATH=. python tools/run_c15_t2_t3_p2c_study.py.
No sensor or ontology authenticity, learned models, or external OctoMap/OpenVDB execution.
"""
from __future__ import annotations
import json,random,math,hashlib,platform,statistics
from pathlib import Path
import numpy as np
import networkx as nx
from scipy.special import expit
from cognitum.proto import structural_hypotheses_pb2 as sp, temporal_occupancy_pb2 as tp
from cognitum.spatial_structural_hypotheses import analyze
from cognitum.spatial_temporal_occupancy import integrate

base=Path(__file__).resolve().parents[1]
rows=[]
for seed in range(200):
 rng=random.Random(911000+seed)
 actual_beam=bool(rng.getrandbits(1))
 q=sp.StructuralHypothesisRequest(schema_version=1,graph_id='assembly',conversation_id='research',research_only=True)
 for hid,present in [('beam',True),('no_beam',False)]:
  h=q.hypotheses.add(hypothesis_id=hid,prior_weight=1)
  h.assertions.add(assembly_id='wall',part_id='hidden_support',role='support',present=present)
 q.functions.add(assembly_id='wall',function_id='support_role_claim',required_roles=['support'])
 votes=[]
 for i in range(6):
  positive=actual_beam if rng.random()<.8 else not actual_beam
  votes.append(positive)
  obs=q.observations.add(source_ref='seed_'+str(seed)+'_observation_'+str(i),tick=i+1)
  obs.likelihoods.add(hypothesis_id='beam',likelihood=.8 if positive else .2)
  obs.likelihoods.add(hypothesis_id='no_beam',likelihood=.2 if positive else .8)
 ans=analyze(q)
 independent=np.array([.8**sum(votes)*.2**(6-sum(votes)),.2**sum(votes)*.8**(6-sum(votes))]);independent/=independent.sum()
 weights={a.hypothesis_id:a.relative_weight for a in ans.ranked}
 assert abs(weights['beam']-independent[0])<1e-12
 graph=nx.DiGraph();graph.add_edge('hidden_support','wall')
 assert nx.is_directed_acyclic_graph(graph)
 rows.append({'seed':seed,'actual_beam':actual_beam,'votes_present':sum(votes),'predicted':ans.ranked[0].hypothesis_id,'ambiguous':ans.ambiguous,'correct_top':(ans.ranked[0].hypothesis_id=='beam')==actual_beam})

occupancy=[]
for seed in range(80):
 rng=random.Random(533000+seed)
 req=tp.TemporalOccupancyRequest(schema_version=1,conversation_id='research',volume_id='synthetic_grid',voxel_size_m=1,max_axis=32,evaluation_tick=100,half_life_ticks=100,research_only=True)
 frame=req.frames.add(frame_id='world',qw=1);frame.translation.x=frame.translation.y=frame.translation.z=0
 coords=rng.sample([(x,y,0) for x in range(1,29) for y in range(1,29)],60)
 rng.shuffle(coords)
 for j,(x,y,z) in enumerate(coords):
  truth=rng.random()<.35
  observed=truth if rng.random()<.80 else not truth
  ray=req.rays.add(source_ref='synthetic_'+str(j),tick=100,frame_id='world',endpoint_hit=observed,hit_probability=.97,free_probability=.03)
  ray.start.x=x+.10;ray.start.y=y+.10;ray.start.z=z+.1
  ray.end.x=x+.20;ray.end.y=y+.10;ray.end.z=z+.1
  target=req.calibration_labels if j<25 else req.holdout_labels
  target.add(x=x,y=y,z=z,occupied=truth,source_ref='synthetic_oracle_'+str(j))
 ans=integrate(req)
 probs={(c.x,c.y,c.z):c for c in ans.cells}
 independent_raw=statistics.mean((expit(c.log_odds)-int(label.occupied))**2 for label in req.holdout_labels for c in [probs[(label.x,label.y,label.z)]])
 independent_cal=statistics.mean((expit(c.log_odds/ans.holdout.selected_temperature)-int(label.occupied))**2 for label in req.holdout_labels for c in [probs[(label.x,label.y,label.z)]])
 assert abs(independent_raw-ans.holdout.brier_score)<1e-12
 assert abs(independent_cal-ans.holdout.calibrated_brier)<1e-12
 occupancy.append({'seed':seed,'temperature':ans.holdout.selected_temperature,'raw_brier':ans.holdout.brier_score,'calibrated_brier':ans.holdout.calibrated_brier,'raw_ece':ans.holdout.expected_calibration_error,'adjusted_ece':ans.holdout.calibrated_expected_calibration_error,'training_count':ans.holdout.training_count,'holdout_count':ans.holdout.evaluated_count})
summary={
 't2':{'cases':len(rows),'correct_top':sum(x['correct_top'] for x in rows),'ambiguous':sum(x['ambiguous'] for x in rows),'numpy_relative_weight_checks':200,'independent_networkx_dag_checks':200},
 't3':{'cases':len(occupancy),'calibration_labels':sum(x['training_count'] for x in occupancy),'disjoint_holdout_labels':sum(x['holdout_count'] for x in occupancy),'mean_raw_brier':statistics.mean(x['raw_brier'] for x in occupancy),'mean_adjusted_brier':statistics.mean(x['calibrated_brier'] for x in occupancy),'mean_raw_ece':statistics.mean(x['raw_ece'] for x in occupancy),'mean_adjusted_ece':statistics.mean(x['adjusted_ece'] for x in occupancy),'holdout_brier_improved_runs':sum(x['calibrated_brier']<x['raw_brier'] for x in occupancy),'numpy_scipy_formula_checks':80},
 'limitations':['Synthetic likelihoods generated from same assumed model family as scorer','Appearance/sensor sources and truth labels are unauthenticated synthetic caller assertions','Training and evaluation indices disjoint within each run but not independently audited real-world labels','Temperature candidates chosen from a fixed grid; no production calibration certification','No genuine Owlready2/HermiT, OctoMap, or OpenVDB execution','No authenticated Lu action authority']
}
report={'milestone':'C15 T2/T3 P2C','study_version':1,'seed_ranges':{'t2':[911000,911199],'t3':[533000,533079]},'summary':summary,'t2_rows':rows,'t3_rows':occupancy,'environment':{'python':platform.python_version(),'scipy':__import__('scipy').__version__,'networkx':nx.__version__}}
out=base/'docs/components/spatial/P2C-reproducible-studies.json'
out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps(summary,indent=2))
