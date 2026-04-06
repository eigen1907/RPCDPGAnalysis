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

#include "DataFormats/MuonDetId/interface/RPCDetId.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHit.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitCollection.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitPhase2.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitPhase2Collection.h"

#include "TTree.h"

#include <string>
#include <cstdint>

class RPCRecHitDumper : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit RPCRecHitDumper(const edm::ParameterSet&);
  ~RPCRecHitDumper() override = default;

  static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;

  void fillEventInfo(const edm::Event&);
  void fillDetInfo(const RPCDetId&, const RPCRoll*);
  void fillPointInfo(const LocalPoint&, const GlobalPoint&);

  template <typename HitType>
  void fillHitCommon(const HitType& hit);

  bool dumpRPCRecHit_;
  bool dumpRPCRecHitPhase2_;

  edm::EDGetTokenT<RPCRecHitCollection> rpcRecHitToken_;
  edm::EDGetTokenT<RPCRecHitPhase2Collection> rpcRecHitPhase2Token_;

  edm::ESGetToken<RPCGeometry, MuonGeometryRecord> rpcGeomToken_;

  TTree* rpcRecHitTree_;
  TTree* rpcRecHitPhase2Tree_;

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

  float local_x_;
  float local_y_;
  float local_z_;
  float global_x_;
  float global_y_;
  float global_z_;

  int bx_;
  int first_strip_;
  int cluster_size_;
  float time_;
  float time_error_;

  float local_err_xx_;
  float local_err_xy_;
  float local_err_yy_;
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
        consumes<RPCRecHitPhase2Collection>(iConfig.getParameter<edm::InputTag>("rpcRecHitPhase2Tag"));
  }

  edm::Service<TFileService> fs;

  auto bookCommonBranches = [&](TTree* tree) {
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

    tree->Branch("local_x", &local_x_);
    tree->Branch("local_y", &local_y_);
    tree->Branch("local_z", &local_z_);
    tree->Branch("global_x", &global_x_);
    tree->Branch("global_y", &global_y_);
    tree->Branch("global_z", &global_z_);

    tree->Branch("bx", &bx_);
    tree->Branch("first_strip", &first_strip_);
    tree->Branch("cluster_size", &cluster_size_);
    tree->Branch("time", &time_);
    tree->Branch("time_error", &time_error_);

    tree->Branch("local_err_xx", &local_err_xx_);
    tree->Branch("local_err_xy", &local_err_xy_);
    tree->Branch("local_err_yy", &local_err_yy_);
  };

  rpcRecHitTree_ = nullptr;
  rpcRecHitPhase2Tree_ = nullptr;

  if (dumpRPCRecHit_) {
    rpcRecHitTree_ = fs->make<TTree>("rpcRecHitTree", "RPCRecHit global-position dump");
    bookCommonBranches(rpcRecHitTree_);
  }

  if (dumpRPCRecHitPhase2_) {
    rpcRecHitPhase2Tree_ = fs->make<TTree>("rpcRecHitPhase2Tree", "RPCRecHitPhase2 global-position dump");
    bookCommonBranches(rpcRecHitPhase2Tree_);
  }
}

void RPCRecHitDumper::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;
  desc.add<bool>("dumpRPCRecHit", true);
  desc.add<edm::InputTag>("rpcRecHitTag", edm::InputTag("rpcRecHits"));

  desc.add<bool>("dumpRPCRecHitPhase2", false);
  desc.add<edm::InputTag>("rpcRecHitPhase2Tag", edm::InputTag("rpcRecHitPhase2"));

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

void RPCRecHitDumper::fillPointInfo(const LocalPoint& lp, const GlobalPoint& gp) {
  local_x_ = lp.x();
  local_y_ = lp.y();
  local_z_ = lp.z();

  global_x_ = gp.x();
  global_y_ = gp.y();
  global_z_ = gp.z();
}

template <typename HitType>
void RPCRecHitDumper::fillHitCommon(const HitType& hit) {
  bx_ = hit.BunchX();
  first_strip_ = hit.firstClusterStrip();
  cluster_size_ = hit.clusterSize();
  time_ = hit.time();
  time_error_ = hit.timeError();

  const LocalError& err = hit.localPositionError();
  local_err_xx_ = err.xx();
  local_err_xy_ = err.xy();
  local_err_yy_ = err.yy();
}

void RPCRecHitDumper::analyze(const edm::Event& iEvent, const edm::EventSetup& iSetup) {
  const auto& rpcGeom = iSetup.getData(rpcGeomToken_);
  fillEventInfo(iEvent);

  if (dumpRPCRecHit_) {
    edm::Handle<RPCRecHitCollection> hRecHits;
    if (iEvent.getByToken(rpcRecHitToken_, hRecHits) && hRecHits.isValid()) {
      for (auto it = hRecHits->begin(); it != hRecHits->end(); ++it) {
        const RPCRecHit& hit = *it;
        const RPCDetId detId = hit.rpcId();
        const RPCRoll* rollDet = rpcGeom.roll(detId);
        if (!rollDet) {
          continue;
        }

        const LocalPoint lp = hit.localPosition();
        const GlobalPoint gp = rollDet->toGlobal(lp);

        fillDetInfo(detId, rollDet);
        fillPointInfo(lp, gp);
        fillHitCommon(hit);

        rpcRecHitTree_->Fill();
      }
    }
  }

  if (dumpRPCRecHitPhase2_) {
    edm::Handle<RPCRecHitPhase2Collection> hRecHitsP2;
    if (iEvent.getByToken(rpcRecHitPhase2Token_, hRecHitsP2) && hRecHitsP2.isValid()) {
      for (auto it = hRecHitsP2->begin(); it != hRecHitsP2->end(); ++it) {
        const RPCRecHitPhase2& hit = *it;
        const RPCDetId detId = hit.rpcId();
        const RPCRoll* rollDet = rpcGeom.roll(detId);
        if (!rollDet) {
          continue;
        }

        const LocalPoint lp = hit.localPosition();
        const GlobalPoint gp = rollDet->toGlobal(lp);

        fillDetInfo(detId, rollDet);
        fillPointInfo(lp, gp);
        fillHitCommon(hit);

        rpcRecHitPhase2Tree_->Fill();
      }
    }
  }
}

DEFINE_FWK_MODULE(RPCRecHitDumper);