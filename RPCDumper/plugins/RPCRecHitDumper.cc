#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"

#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"

#include "FWCore/Utilities/interface/InputTag.h"
#include "FWCore/ServiceRegistry/interface/Service.h"

#include "CommonTools/UtilAlgos/interface/TFileService.h"

#include "Geometry/Records/interface/MuonGeometryRecord.h"
#include "Geometry/RPCGeometry/interface/RPCGeometry.h"
#include "Geometry/RPCGeometry/interface/RPCRoll.h"
#include "Geometry/RPCGeometry/interface/RPCGeomServ.h"

#include "DataFormats/DetId/interface/DetId.h"
#include "DataFormats/MuonDetId/interface/MuonSubdetId.h"
#include "DataFormats/MuonDetId/interface/RPCDetId.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHit.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitCollection.h"

#include "SimDataFormats/TrackingHit/interface/PSimHitContainer.h"
#include "SimDataFormats/TrackingAnalysis/interface/TrackingParticle.h"
#include "SimGeneral/TrackingAnalysis/interface/SimHitTPAssociationProducer.h"

#include "TTree.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

class RPCRecHitDumper : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit RPCRecHitDumper(const edm::ParameterSet&);
  ~RPCRecHitDumper() override = default;

  static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
  struct SimHitMatchCandidate {
    TrackingParticleRef tp;
    TrackPSimHitRef simHit;
  };

  void analyze(const edm::Event&, const edm::EventSetup&) override;

  void fillEventInfo(const edm::Event&);
  void fillDetInfo(const RPCDetId&, const RPCRoll*);
  void fillRecHitPointInfo(const LocalPoint&, const GlobalPoint&);
  void fillSimHitInfo(const RPCRecHit&, const RPCRoll*, const std::vector<SimHitMatchCandidate>*);
  void resetSimHitInfo();

  template <typename HitType>
  void fillRecHitCommon(const HitType& hit);

  template <typename CollectionType>
  void dumpRecHits(const CollectionType&,
                   const RPCGeometry&,
                   TTree*,
                   const std::map<uint32_t, std::vector<SimHitMatchCandidate> >&);

  bool dumpRPCRecHit_;
  bool dumpRPCRecHitPhase2_;

  edm::EDGetTokenT<RPCRecHitCollection> rpcRecHitToken_;
  edm::EDGetTokenT<RPCRecHitCollection> rpcRecHitPhase2Token_;

  edm::EDGetTokenT<edm::PSimHitContainer> simHitToken_;
  edm::EDGetTokenT<TrackingParticleCollection> trackingParticleToken_;
  edm::EDGetTokenT<SimHitTPAssociationProducer::SimHitTPAssociationList> simHitAssocToken_;

  edm::ESGetToken<RPCGeometry, MuonGeometryRecord> rpcGeomToken_;

  TTree* rpcRecHitsTree_;
  TTree* rpcRecHitsPhase2Tree_;

  int run_;
  int lumi_;
  ULong64_t event_;

  std::string roll_name_;
  int region_;
  int ring_;
  int station_;
  int sector_;
  int layer_;
  int subsector_;
  int roll_;
  uint32_t rawId_;
  bool is_barrel_;
  bool is_irpc_;

  float rechit_local_x_;
  float rechit_local_y_;
  float rechit_local_z_;
  float rechit_global_x_;
  float rechit_global_y_;
  float rechit_global_z_;

  int rechit_bx_;
  int rechit_first_strip_;
  int rechit_cls_;
  float rechit_time_;
  float rechit_time_error_;

  float rechit_local_err_xx_;
  float rechit_local_err_xy_;
  float rechit_local_err_yy_;

  bool has_simhit_match_;
  int n_simhit_candidates_same_roll_;

  float simhit_local_x_;
  float simhit_local_y_;
  float simhit_local_z_;
  float simhit_global_x_;
  float simhit_global_y_;
  float simhit_global_z_;
  float simhit_dx_;
  float simhit_dy_;
  float simhit_dr_;
  float simhit_tof_;
  int simhit_particle_type_;

  int tp_pdgId_;
  float tp_pt_;
  float tp_p_;
  float tp_eta_;
  float tp_phi_;
  float tp_charge_;
  int tp_status_;
};

RPCRecHitDumper::RPCRecHitDumper(const edm::ParameterSet& iConfig)
    : dumpRPCRecHit_(iConfig.getParameter<bool>("dumpRPCRecHit")),
      dumpRPCRecHitPhase2_(iConfig.getParameter<bool>("dumpRPCRecHitPhase2")),
      rpcGeomToken_(esConsumes()) {
  usesResource("TFileService");

  if (dumpRPCRecHit_) {
    rpcRecHitToken_ = consumes<RPCRecHitCollection>(iConfig.getParameter<edm::InputTag>("rpcRecHitTag"));
  }
  if (dumpRPCRecHitPhase2_) {
    rpcRecHitPhase2Token_ =
        consumes<RPCRecHitCollection>(iConfig.getParameter<edm::InputTag>("rpcRecHitPhase2Tag"));
  }

  simHitToken_ = consumes<edm::PSimHitContainer>(iConfig.getParameter<edm::InputTag>("simHitTag"));
  trackingParticleToken_ =
      consumes<TrackingParticleCollection>(iConfig.getParameter<edm::InputTag>("trackingParticleTag"));
  simHitAssocToken_ = consumes<SimHitTPAssociationProducer::SimHitTPAssociationList>(
      iConfig.getParameter<edm::InputTag>("simHitAssocTag"));

  edm::Service<TFileService> fs;

  auto bookBranches = [&](TTree* tree) {
    tree->Branch("run", &run_);
    tree->Branch("lumi", &lumi_);
    tree->Branch("event", &event_);

    tree->Branch("roll_name", &roll_name_);
    tree->Branch("region", &region_);
    tree->Branch("ring", &ring_);
    tree->Branch("station", &station_);
    tree->Branch("sector", &sector_);
    tree->Branch("layer", &layer_);
    tree->Branch("subsector", &subsector_);
    tree->Branch("roll", &roll_);
    tree->Branch("rawId", &rawId_);
    tree->Branch("is_barrel", &is_barrel_);
    tree->Branch("is_irpc", &is_irpc_);

    tree->Branch("rechit_local_x", &rechit_local_x_);
    tree->Branch("rechit_local_y", &rechit_local_y_);
    tree->Branch("rechit_local_z", &rechit_local_z_);
    tree->Branch("rechit_global_x", &rechit_global_x_);
    tree->Branch("rechit_global_y", &rechit_global_y_);
    tree->Branch("rechit_global_z", &rechit_global_z_);

    tree->Branch("rechit_bx", &rechit_bx_);
    tree->Branch("rechit_first_strip", &rechit_first_strip_);
    tree->Branch("rechit_cls", &rechit_cls_);
    tree->Branch("rechit_time", &rechit_time_);
    tree->Branch("rechit_time_error", &rechit_time_error_);

    tree->Branch("rechit_local_err_xx", &rechit_local_err_xx_);
    tree->Branch("rechit_local_err_xy", &rechit_local_err_xy_);
    tree->Branch("rechit_local_err_yy", &rechit_local_err_yy_);

    tree->Branch("has_simhit_match", &has_simhit_match_);
    tree->Branch("n_simhit_candidates_same_roll", &n_simhit_candidates_same_roll_);

    tree->Branch("simhit_local_x", &simhit_local_x_);
    tree->Branch("simhit_local_y", &simhit_local_y_);
    tree->Branch("simhit_local_z", &simhit_local_z_);
    tree->Branch("simhit_global_x", &simhit_global_x_);
    tree->Branch("simhit_global_y", &simhit_global_y_);
    tree->Branch("simhit_global_z", &simhit_global_z_);
    tree->Branch("simhit_dx", &simhit_dx_);
    tree->Branch("simhit_dy", &simhit_dy_);
    tree->Branch("simhit_dr", &simhit_dr_);
    tree->Branch("simhit_tof", &simhit_tof_);
    tree->Branch("simhit_particle_type", &simhit_particle_type_);

    tree->Branch("tp_pdgId", &tp_pdgId_);
    tree->Branch("tp_pt", &tp_pt_);
    tree->Branch("tp_p", &tp_p_);
    tree->Branch("tp_eta", &tp_eta_);
    tree->Branch("tp_phi", &tp_phi_);
    tree->Branch("tp_charge", &tp_charge_);
    tree->Branch("tp_status", &tp_status_);
  };

  rpcRecHitsTree_ = nullptr;
  rpcRecHitsPhase2Tree_ = nullptr;

  if (dumpRPCRecHit_) {
    rpcRecHitsTree_ = fs->make<TTree>("rpcRecHitsTree", "RPCRecHit dump");
    bookBranches(rpcRecHitsTree_);
  }

  if (dumpRPCRecHitPhase2_) {
    rpcRecHitsPhase2Tree_ = fs->make<TTree>("rpcRecHitsPhase2Tree", "RPCRecHitPhase2 dump");
    bookBranches(rpcRecHitsPhase2Tree_);
  }
}

void RPCRecHitDumper::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;
  desc.add<bool>("dumpRPCRecHit", true);
  desc.add<edm::InputTag>("rpcRecHitTag", edm::InputTag("rpcRecHits"));
  desc.add<bool>("dumpRPCRecHitPhase2", false);
  desc.add<edm::InputTag>("rpcRecHitPhase2Tag", edm::InputTag("rpcRecHitsPhase2"));

  desc.add<edm::InputTag>("simHitTag", edm::InputTag("g4SimHits", "MuonRPCHits"));
  desc.add<edm::InputTag>("trackingParticleTag", edm::InputTag("mix", "MergedTrackTruth"));
  desc.add<edm::InputTag>("simHitAssocTag", edm::InputTag("simHitTPAssocProducer"));

  descriptions.add("RPCRecHitDumper", desc);
}

void RPCRecHitDumper::fillEventInfo(const edm::Event& iEvent) {
  run_ = static_cast<int>(iEvent.id().run());
  lumi_ = static_cast<int>(iEvent.luminosityBlock());
  event_ = static_cast<ULong64_t>(iEvent.id().event());
}

void RPCRecHitDumper::fillDetInfo(const RPCDetId& detId, const RPCRoll* rollDet) {
  roll_name_ = RPCGeomServ(detId).name();
  region_ = detId.region();
  ring_ = detId.ring();
  station_ = detId.station();
  sector_ = detId.sector();
  layer_ = detId.layer();
  subsector_ = detId.subsector();
  roll_ = detId.roll();
  rawId_ = detId.rawId();
  is_barrel_ = rollDet->isBarrel();
  is_irpc_ = rollDet->isIRPC();
}

void RPCRecHitDumper::fillRecHitPointInfo(const LocalPoint& lp, const GlobalPoint& gp) {
  rechit_local_x_ = lp.x();
  rechit_local_y_ = lp.y();
  rechit_local_z_ = lp.z();
  rechit_global_x_ = gp.x();
  rechit_global_y_ = gp.y();
  rechit_global_z_ = gp.z();
}

template <typename HitType>
void RPCRecHitDumper::fillRecHitCommon(const HitType& hit) {
  rechit_bx_ = hit.BunchX();
  rechit_first_strip_ = hit.firstClusterStrip();
  rechit_cls_ = hit.clusterSize();
  rechit_time_ = hit.time();
  rechit_time_error_ = hit.timeError();

  const LocalError& err = hit.localPositionError();
  rechit_local_err_xx_ = err.xx();
  rechit_local_err_xy_ = err.xy();
  rechit_local_err_yy_ = err.yy();
}

void RPCRecHitDumper::resetSimHitInfo() {
  has_simhit_match_ = false;
  n_simhit_candidates_same_roll_ = 0;

  simhit_local_x_ = -999.f;
  simhit_local_y_ = -999.f;
  simhit_local_z_ = -999.f;
  simhit_global_x_ = -999.f;
  simhit_global_y_ = -999.f;
  simhit_global_z_ = -999.f;
  simhit_dx_ = 999.f;
  simhit_dy_ = 999.f;
  simhit_dr_ = 999.f;
  simhit_tof_ = -999.f;
  simhit_particle_type_ = 0;

  tp_pdgId_ = 0;
  tp_pt_ = -999.f;
  tp_p_ = -999.f;
  tp_eta_ = -999.f;
  tp_phi_ = -999.f;
  tp_charge_ = 0.f;
  tp_status_ = -999;
}

void RPCRecHitDumper::fillSimHitInfo(const RPCRecHit& hit,
                                     const RPCRoll* rollDet,
                                     const std::vector<SimHitMatchCandidate>* candidates) {
  resetSimHitInfo();

  if (candidates == nullptr || candidates->empty()) {
    return;
  }

  n_simhit_candidates_same_roll_ = static_cast<int>(candidates->size());

  const LocalPoint recHitLocalPoint = hit.localPosition();
  const SimHitMatchCandidate* bestCandidate = nullptr;
  double bestAbsDx = 1.0e9;

  for (std::vector<SimHitMatchCandidate>::const_iterator it = candidates->begin(); it != candidates->end(); ++it) {
    if (it->simHit.isNull() || it->tp.isNull()) {
      continue;
    }

    const double dx = recHitLocalPoint.x() - it->simHit->localPosition().x();
    const double absDx = std::abs(dx);
    if (absDx < bestAbsDx) {
      bestAbsDx = absDx;
      bestCandidate = &(*it);
    }
  }

  if (bestCandidate == nullptr) {
    return;
  }

  has_simhit_match_ = true;

  const LocalPoint simHitLocalPoint = bestCandidate->simHit->localPosition();
  const GlobalPoint simHitGlobalPoint = rollDet->toGlobal(simHitLocalPoint);

  simhit_local_x_ = simHitLocalPoint.x();
  simhit_local_y_ = simHitLocalPoint.y();
  simhit_local_z_ = simHitLocalPoint.z();
  simhit_global_x_ = simHitGlobalPoint.x();
  simhit_global_y_ = simHitGlobalPoint.y();
  simhit_global_z_ = simHitGlobalPoint.z();

  simhit_dx_ = recHitLocalPoint.x() - simHitLocalPoint.x();
  simhit_dy_ = recHitLocalPoint.y() - simHitLocalPoint.y();
  simhit_dr_ = std::hypot(simhit_dx_, simhit_dy_);
  simhit_tof_ = bestCandidate->simHit->timeOfFlight();
  simhit_particle_type_ = bestCandidate->simHit->particleType();

  tp_pdgId_ = bestCandidate->tp->pdgId();
  tp_pt_ = bestCandidate->tp->pt();
  tp_p_ = bestCandidate->tp->p();
  tp_eta_ = bestCandidate->tp->eta();
  tp_phi_ = bestCandidate->tp->phi();
  tp_charge_ = bestCandidate->tp->charge();
  tp_status_ = bestCandidate->tp->status();
}

template <typename CollectionType>
void RPCRecHitDumper::dumpRecHits(const CollectionType& recHits,
                                  const RPCGeometry& rpcGeom,
                                  TTree* tree,
                                  const std::map<uint32_t, std::vector<SimHitMatchCandidate> >& simHitCandidatesByRawId) {
  if (tree == nullptr) {
    return;
  }

  for (typename CollectionType::const_iterator it = recHits.begin(); it != recHits.end(); ++it) {
    const RPCRecHit& hit = *it;
    const RPCDetId detId = hit.rpcId();
    const RPCRoll* rollDet = rpcGeom.roll(detId);
    if (!rollDet) {
      continue;
    }

    fillDetInfo(detId, rollDet);
    fillRecHitPointInfo(hit.localPosition(), rollDet->toGlobal(hit.localPosition()));
    fillRecHitCommon(hit);

    const std::map<uint32_t, std::vector<SimHitMatchCandidate> >::const_iterator found =
        simHitCandidatesByRawId.find(detId.rawId());
    if (found == simHitCandidatesByRawId.end()) {
      fillSimHitInfo(hit, rollDet, 0);
    } else {
      fillSimHitInfo(hit, rollDet, &(found->second));
    }

    tree->Fill();
  }
}

void RPCRecHitDumper::analyze(const edm::Event& iEvent, const edm::EventSetup& iSetup) {
  const RPCGeometry& rpcGeom = iSetup.getData(rpcGeomToken_);
  fillEventInfo(iEvent);

  edm::Handle<edm::PSimHitContainer> simHitHandle;
  edm::Handle<TrackingParticleCollection> trackingParticleHandle;
  edm::Handle<SimHitTPAssociationProducer::SimHitTPAssociationList> simHitAssocHandle;

  if (!iEvent.getByToken(simHitToken_, simHitHandle) || !simHitHandle.isValid()) {
    return;
  }
  if (!iEvent.getByToken(trackingParticleToken_, trackingParticleHandle) || !trackingParticleHandle.isValid()) {
    return;
  }
  if (!iEvent.getByToken(simHitAssocToken_, simHitAssocHandle) || !simHitAssocHandle.isValid()) {
    return;
  }

  std::map<uint32_t, std::vector<SimHitMatchCandidate> > simHitCandidatesByRawId;

  for (int i = 0, n = trackingParticleHandle->size(); i < n; ++i) {
    TrackingParticleRef tp(trackingParticleHandle, i);

    if (tp->pt() < 1.0 || tp->p() < 2.5) {
      continue;
    }

    std::vector<TrackPSimHitRef> simHitsFromParticle;
    std::pair<SimHitTPAssociationProducer::SimHitTPAssociationList::const_iterator,
              SimHitTPAssociationProducer::SimHitTPAssociationList::const_iterator>
        range = std::equal_range(simHitAssocHandle->begin(),
                                 simHitAssocHandle->end(),
                                 std::make_pair(tp, TrackPSimHitRef()),
                                 SimHitTPAssociationProducer::simHitTPAssociationListGreater);

    for (SimHitTPAssociationProducer::SimHitTPAssociationList::const_iterator itAssoc = range.first;
         itAssoc != range.second;
         ++itAssoc) {
      TrackPSimHitRef simHit = itAssoc->second;
      if (simHit.isNull()) {
        continue;
      }

      const DetId detId(simHit->detUnitId());
      if (detId.det() != DetId::Muon || detId.subdetId() != MuonSubdetId::RPC) {
        continue;
      }

      simHitsFromParticle.push_back(simHit);
    }

    if (std::abs(tp->pdgId()) != 13) {
      continue;
    }

    for (std::vector<TrackPSimHitRef>::const_iterator itSimHit = simHitsFromParticle.begin();
         itSimHit != simHitsFromParticle.end();
         ++itSimHit) {
      simHitCandidatesByRawId[(*itSimHit)->detUnitId()].push_back(SimHitMatchCandidate{tp, *itSimHit});
    }
  }

  if (dumpRPCRecHit_) {
    edm::Handle<RPCRecHitCollection> recHitHandle;
    if (iEvent.getByToken(rpcRecHitToken_, recHitHandle) && recHitHandle.isValid()) {
      dumpRecHits(*recHitHandle, rpcGeom, rpcRecHitsTree_, simHitCandidatesByRawId);
    }
  }

  if (dumpRPCRecHitPhase2_) {
    edm::Handle<RPCRecHitCollection> recHitPhase2Handle;
    if (iEvent.getByToken(rpcRecHitPhase2Token_, recHitPhase2Handle) && recHitPhase2Handle.isValid()) {
      dumpRecHits(*recHitPhase2Handle, rpcGeom, rpcRecHitsPhase2Tree_, simHitCandidatesByRawId);
    }
  }
}

DEFINE_FWK_MODULE(RPCRecHitDumper);
