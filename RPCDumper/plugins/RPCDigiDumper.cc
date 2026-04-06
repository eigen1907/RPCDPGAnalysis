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
#include "DataFormats/RPCDigi/interface/RPCDigi.h"
#include "DataFormats/RPCDigi/interface/RPCDigiCollection.h"
#include "DataFormats/RPCDigi/interface/IRPCDigi.h"
#include "DataFormats/RPCDigi/interface/IRPCDigiCollection.h"
#include "DataFormats/RPCDigi/interface/RPCDigiPhase2.h"
#include "DataFormats/RPCDigi/interface/RPCDigiPhase2Collection.h"

#include "TTree.h"

#include <string>
#include <cstdint>

class RPCDigiDumper : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit RPCDigiDumper(const edm::ParameterSet&);
  ~RPCDigiDumper() override = default;

  static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;

  void fillEventInfo(const edm::Event&);
  void fillDetInfo(const RPCDetId&, const RPCRoll*);
  void fillPointInfo(const LocalPoint&, const GlobalPoint&);

  LocalPoint makeStripCenterPoint(const RPCRoll*, int strip) const;
  LocalPoint makeRPCDigiPoint(const RPCRoll*, const RPCDigi&) const;

  bool dumpRPCDigi_;
  bool dumpIRPCDigi_;
  bool dumpRPCDigiPhase2_;

  edm::EDGetTokenT<RPCDigiCollection> rpcDigiToken_;
  edm::EDGetTokenT<IRPCDigiCollection> irpcDigiToken_;
  edm::EDGetTokenT<RPCDigiPhase2Collection> rpcDigiPhase2Token_;

  edm::ESGetToken<RPCGeometry, MuonGeometryRecord> rpcGeomToken_;

  TTree* rpcDigiTree_;
  TTree* irpcDigiTree_;
  TTree* rpcDigiPhase2Tree_;

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

  int strip_;
  int bx_;

  bool has_time_;
  bool has_x_;
  bool has_y_;
  bool is_pseudodigi_;
  float time_;
  float coordinate_x_;
  float coordinate_y_;
  float delta_time_;
  float delta_x_;
  float delta_y_;

  int bxLR_;
  int bxHR_;
  int sbx_;
  int sbxLR_;
  int sbxHR_;
  int fineLR_;
  int fineHR_;
};

RPCDigiDumper::RPCDigiDumper(const edm::ParameterSet& iConfig)
    : dumpRPCDigi_(iConfig.getParameter<bool>("dumpRPCDigi")),
      dumpIRPCDigi_(iConfig.getParameter<bool>("dumpIRPCDigi")),
      dumpRPCDigiPhase2_(iConfig.getParameter<bool>("dumpRPCDigiPhase2")),
      rpcGeomToken_(esConsumes()) {
  usesResource("TFileService");

  if (dumpRPCDigi_) {
    rpcDigiToken_ = consumes<RPCDigiCollection>(iConfig.getParameter<edm::InputTag>("rpcDigiTag"));
  }
  if (dumpIRPCDigi_) {
    irpcDigiToken_ = consumes<IRPCDigiCollection>(iConfig.getParameter<edm::InputTag>("irpcDigiTag"));
  }
  if (dumpRPCDigiPhase2_) {
    rpcDigiPhase2Token_ = consumes<RPCDigiPhase2Collection>(iConfig.getParameter<edm::InputTag>("rpcDigiPhase2Tag"));
  }

  edm::Service<TFileService> fs;

  rpcDigiTree_ = nullptr;
  irpcDigiTree_ = nullptr;
  rpcDigiPhase2Tree_ = nullptr;

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

    tree->Branch("strip", &strip_);
    tree->Branch("bx", &bx_);
  };

  if (dumpRPCDigi_) {
    rpcDigiTree_ = fs->make<TTree>("rpcDigiTree", "RPCDigi global-position dump");
    bookCommonBranches(rpcDigiTree_);

    rpcDigiTree_->Branch("has_time", &has_time_);
    rpcDigiTree_->Branch("has_x", &has_x_);
    rpcDigiTree_->Branch("has_y", &has_y_);
    rpcDigiTree_->Branch("is_pseudodigi", &is_pseudodigi_);
    rpcDigiTree_->Branch("time", &time_);
    rpcDigiTree_->Branch("coordinate_x", &coordinate_x_);
    rpcDigiTree_->Branch("coordinate_y", &coordinate_y_);
    rpcDigiTree_->Branch("delta_time", &delta_time_);
    rpcDigiTree_->Branch("delta_x", &delta_x_);
    rpcDigiTree_->Branch("delta_y", &delta_y_);
  }

  if (dumpIRPCDigi_) {
    irpcDigiTree_ = fs->make<TTree>("irpcDigiTree", "IRPCDigi global-position dump");
    bookCommonBranches(irpcDigiTree_);

    irpcDigiTree_->Branch("bxLR", &bxLR_);
    irpcDigiTree_->Branch("bxHR", &bxHR_);
    irpcDigiTree_->Branch("sbx", &sbx_);
    irpcDigiTree_->Branch("sbxLR", &sbxLR_);
    irpcDigiTree_->Branch("sbxHR", &sbxHR_);
    irpcDigiTree_->Branch("fineLR", &fineLR_);
    irpcDigiTree_->Branch("fineHR", &fineHR_);
  }

  if (dumpRPCDigiPhase2_) {
    rpcDigiPhase2Tree_ = fs->make<TTree>("rpcDigiPhase2Tree", "RPCDigiPhase2 global-position dump");
    bookCommonBranches(rpcDigiPhase2Tree_);

    rpcDigiPhase2Tree_->Branch("sbx", &sbx_);
  }
}

void RPCDigiDumper::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;
  desc.add<bool>("dumpRPCDigi", true);
  desc.add<edm::InputTag>("rpcDigiTag", edm::InputTag("simMuonRPCDigis"));

  desc.add<bool>("dumpIRPCDigi", false);
  desc.add<edm::InputTag>("irpcDigiTag", edm::InputTag("simMuonIRPCDigis"));

  desc.add<bool>("dumpRPCDigiPhase2", false);
  desc.add<edm::InputTag>("rpcDigiPhase2Tag", edm::InputTag("simMuonRPCDigisPhase2"));

  descriptions.add("RPCDigiDumper", desc);
}

void RPCDigiDumper::fillEventInfo(const edm::Event& iEvent) {
  run_ = static_cast<int>(iEvent.id().run());
  lumi_ = static_cast<int>(iEvent.luminosityBlock());
  event_ = static_cast<ULong64_t>(iEvent.id().event());
}

void RPCDigiDumper::fillDetInfo(const RPCDetId& detId, const RPCRoll* rollDet) {
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

void RPCDigiDumper::fillPointInfo(const LocalPoint& lp, const GlobalPoint& gp) {
  local_x_ = lp.x();
  local_y_ = lp.y();
  local_z_ = lp.z();

  global_x_ = gp.x();
  global_y_ = gp.y();
  global_z_ = gp.z();
}

LocalPoint RPCDigiDumper::makeStripCenterPoint(const RPCRoll* rollDet, int strip) const {
  return rollDet->centreOfStrip(strip);
}

LocalPoint RPCDigiDumper::makeRPCDigiPoint(const RPCRoll* rollDet, const RPCDigi& digi) const {
  LocalPoint lp = rollDet->centreOfStrip(digi.strip());

  const float x = digi.hasX() ? static_cast<float>(digi.coordinateX()) : lp.x();
  const float y = digi.hasY() ? static_cast<float>(digi.coordinateY()) : lp.y();

  return LocalPoint(x, y, 0.f);
}

void RPCDigiDumper::analyze(const edm::Event& iEvent, const edm::EventSetup& iSetup) {
  const auto& rpcGeom = iSetup.getData(rpcGeomToken_);
  fillEventInfo(iEvent);

  if (dumpRPCDigi_) {
    edm::Handle<RPCDigiCollection> hDigis;
    if (iEvent.getByToken(rpcDigiToken_, hDigis) && hDigis.isValid()) {
      for (auto it = hDigis->begin(); it != hDigis->end(); ++it) {
        const auto detRange = *it;
        const RPCDetId detId = detRange.first;
        const RPCRoll* rollDet = rpcGeom.roll(detId);
        if (!rollDet) {
          continue;
        }

        for (auto digiIt = detRange.second.first; digiIt != detRange.second.second; ++digiIt) {
          const RPCDigi& digi = *digiIt;

          const LocalPoint lp = makeRPCDigiPoint(rollDet, digi);
          const GlobalPoint gp = rollDet->toGlobal(lp);

          fillDetInfo(detId, rollDet);
          fillPointInfo(lp, gp);

          strip_ = digi.strip();
          bx_ = digi.bx();

          has_time_ = digi.hasTime();
          has_x_ = digi.hasX();
          has_y_ = digi.hasY();
          is_pseudodigi_ = digi.isPseudoDigi();

          time_ = static_cast<float>(digi.time());
          coordinate_x_ = static_cast<float>(digi.coordinateX());
          coordinate_y_ = static_cast<float>(digi.coordinateY());
          delta_time_ = static_cast<float>(digi.deltaTime());
          delta_x_ = static_cast<float>(digi.deltaX());
          delta_y_ = static_cast<float>(digi.deltaY());

          rpcDigiTree_->Fill();
        }
      }
    }
  }

  if (dumpIRPCDigi_) {
    edm::Handle<IRPCDigiCollection> hIRPCDigis;
    if (iEvent.getByToken(irpcDigiToken_, hIRPCDigis) && hIRPCDigis.isValid()) {
      for (auto it = hIRPCDigis->begin(); it != hIRPCDigis->end(); ++it) {
        const auto detRange = *it;
        const RPCDetId detId = detRange.first;
        const RPCRoll* rollDet = rpcGeom.roll(detId);
        if (!rollDet) {
          continue;
        }

        for (auto digiIt = detRange.second.first; digiIt != detRange.second.second; ++digiIt) {
          const IRPCDigi& digi = *digiIt;

          const LocalPoint lp = makeStripCenterPoint(rollDet, digi.strip());
          const GlobalPoint gp = rollDet->toGlobal(lp);

          fillDetInfo(detId, rollDet);
          fillPointInfo(lp, gp);

          strip_ = digi.strip();
          bx_ = digi.bx();

          bxLR_ = digi.bxLR();
          bxHR_ = digi.bxHR();
          sbx_ = digi.sbx();
          sbxLR_ = digi.sbxLR();
          sbxHR_ = digi.sbxHR();
          fineLR_ = digi.fineLR();
          fineHR_ = digi.fineHR();

          irpcDigiTree_->Fill();
        }
      }
    }
  }

  if (dumpRPCDigiPhase2_) {
    edm::Handle<RPCDigiPhase2Collection> hDigisP2;
    if (iEvent.getByToken(rpcDigiPhase2Token_, hDigisP2) && hDigisP2.isValid()) {
      for (auto it = hDigisP2->begin(); it != hDigisP2->end(); ++it) {
        const auto detRange = *it;
        const RPCDetId detId = detRange.first;
        const RPCRoll* rollDet = rpcGeom.roll(detId);
        if (!rollDet) {
          continue;
        }

        for (auto digiIt = detRange.second.first; digiIt != detRange.second.second; ++digiIt) {
          const RPCDigiPhase2& digi = *digiIt;

          const LocalPoint lp = makeStripCenterPoint(rollDet, digi.strip());
          const GlobalPoint gp = rollDet->toGlobal(lp);

          fillDetInfo(detId, rollDet);
          fillPointInfo(lp, gp);

          strip_ = digi.strip();
          bx_ = digi.bx();
          sbx_ = digi.sbx();

          rpcDigiPhase2Tree_->Fill();
        }
      }
    }
  }
}

DEFINE_FWK_MODULE(RPCDigiDumper);