cmsenv

python3 rpc-rechit-from-reco.py \
  -i step3.root \
  -g Run4D125.csv \
  -o ./plots-rpc-rechit \
  --run3-module-label rpcRecHits \
  --phase2-module-label rpcRecHitsPhase2 \
  --phase2-header DataFormats/RPCRecHit/interface/RPCRecHitPhase2.h \
  --year Phase2 \
  --com 14 \
  --label "Private Work"