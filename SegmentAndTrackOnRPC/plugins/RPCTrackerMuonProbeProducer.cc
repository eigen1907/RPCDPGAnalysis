#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"

#include "FWCore/Framework/interface/Event.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "DataFormats/DTRecHit/interface/DTRecSegment4DCollection.h"
#include "DataFormats/CSCRecHit/interface/CSCSegmentCollection.h"

#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/VertexReco/interface/VertexFwd.h"

#include "DataFormats/MuonReco/interface/Muon.h"
#include "DataFormats/MuonReco/interface/MuonFwd.h"
#include "DataFormats/MuonReco/interface/MuonSelectors.h"
#include "DataFormats/MuonReco/interface/MuonPFIsolation.h"

#include "HLTrigger/HLTcore/interface/HLTConfigProvider.h"
#include "DataFormats/Common/interface/TriggerResults.h"
#include "FWCore/Common/interface/TriggerNames.h"
#include "DataFormats/HLTReco/interface/TriggerObject.h"
#include "DataFormats/HLTReco/interface/TriggerEvent.h"

#include "DataFormats/TrackReco/interface/Track.h"
#include "DataFormats/TrackReco/interface/TrackFwd.h"

#include "DataFormats/MuonDetId/interface/RPCDetId.h"

#include "FWCore/Framework/interface/ESHandle.h"
#include "Geometry/Records/interface/MuonGeometryRecord.h"
#include "Geometry/RPCGeometry/interface/RPCGeometry.h"

#include "DataFormats/Math/interface/deltaR.h"

#include <vector>
#include <string>
#include <memory>
#include <cmath>

class RPCTrackerMuonProbeProducer : public edm::stream::EDProducer<>
{
public:
  RPCTrackerMuonProbeProducer(const edm::ParameterSet& pset);
  void produce(edm::Event& event, const edm::EventSetup&) override;
  void beginRun(const edm::Run& run, const edm::EventSetup& eventSetup) override;

  constexpr static double muonMass_ = 0.1056583715;

private:
  const edm::EDGetTokenT<edm::TriggerResults> triggerResultsToken_;
  const edm::EDGetTokenT<reco::VertexCollection> pvToken_;
  const edm::EDGetTokenT<reco::MuonCollection> muonToken_;
  const edm::EDGetTokenT<trigger::TriggerEvent> triggerEventToken_;

  const double minMuonPt_, maxMuonAbsEta_, maxMuonRelIso_;
  const double minTrackPt_, maxTrackAbsEta_;
  const bool doCheckSign_;
  const double minMass_, maxMass_;
  const double minDR_;
  const std::vector<std::string> triggerPaths_, triggerModules_;

  enum class IDType { RPC, Tracker, Tight, Soft } idType_, tagIdType_;

  HLTConfigProvider hltConfig_;
};

RPCTrackerMuonProbeProducer::RPCTrackerMuonProbeProducer(const edm::ParameterSet& pset):
  triggerResultsToken_(consumes<edm::TriggerResults>(pset.getParameter<edm::InputTag>("triggerResults"))),
  pvToken_(consumes<reco::VertexCollection>(pset.getParameter<edm::InputTag>("vertex"))),
  muonToken_(consumes<reco::MuonCollection>(pset.getParameter<edm::InputTag>("muons"))),
  triggerEventToken_(consumes<trigger::TriggerEvent>(pset.getParameter<edm::InputTag>("triggerObjects"))),
  minMuonPt_(pset.getParameter<double>("minMuonPt")),
  maxMuonAbsEta_(pset.getParameter<double>("maxMuonAbsEta")),
  maxMuonRelIso_(pset.getParameter<double>("maxMuonRelIso")),
  minTrackPt_(pset.getParameter<double>("minTrackPt")),
  maxTrackAbsEta_(pset.getParameter<double>("maxTrackAbsEta")),
  doCheckSign_(pset.getParameter<bool>("doCheckSign")),
  minMass_(pset.getParameter<double>("minMass")),
  maxMass_(pset.getParameter<double>("maxMass")),
  minDR_(pset.getParameter<double>("minDR")),
  triggerPaths_(pset.getParameter<std::vector<std::string>>("triggerPaths")),
  triggerModules_(pset.getParameter<std::vector<std::string>>("triggerModules"))
{
  const std::string idTypeName = pset.getParameter<std::string>("probeIdType");
  if      ( idTypeName == "RPC"     ) idType_ = IDType::RPC;
  else if ( idTypeName == "Tracker" ) idType_ = IDType::Tracker;
  else if ( idTypeName == "Tight"   ) idType_ = IDType::Tight;
  else if ( idTypeName == "Soft"    ) idType_ = IDType::Soft;

  const std::string tagIdTypeName = pset.getParameter<std::string>("tagIdType");
  if      ( tagIdTypeName == "RPC"     ) tagIdType_ = IDType::RPC;
  else if ( tagIdTypeName == "Tracker" ) tagIdType_ = IDType::Tracker;
  else if ( tagIdTypeName == "Tight"   ) tagIdType_ = IDType::Tight;
  else if ( tagIdTypeName == "Soft"    ) tagIdType_ = IDType::Soft;

  produces<reco::MuonCollection>();
  produces<reco::MuonCollection>("tag");
  produces<double>("mass");
}

void RPCTrackerMuonProbeProducer::beginRun(const edm::Run& run, const  edm::EventSetup& eventSetup)
{
  bool changed = true;
  hltConfig_.init(run, eventSetup, "HLT", changed);
}

void RPCTrackerMuonProbeProducer::produce(edm::Event& event, const edm::EventSetup& eventSetup)
{
  using namespace std;

  std::unique_ptr<reco::MuonCollection> out_tag(new reco::MuonCollection);
  std::unique_ptr<reco::MuonCollection> out_probe(new reco::MuonCollection);
  double mass = -1;

  edm::Handle<edm::TriggerResults> triggerResultsHandle;
  event.getByToken(triggerResultsToken_, triggerResultsHandle);

  edm::Handle<reco::VertexCollection> pvHandle;
  event.getByToken(pvToken_, pvHandle);

  edm::Handle<reco::MuonCollection> muonHandle;
  event.getByToken(muonToken_, muonHandle);

  edm::Handle<trigger::TriggerEvent> triggerEventHandle;
  event.getByToken(triggerEventToken_, triggerEventHandle);

  reco::MuonRef tagRef;
  reco::MuonRef probeRef;
  do {
    if ( pvHandle->empty() ) break;
    const auto pv = pvHandle->at(0);

    // Collect interested trigger objects
    auto triggerNames = event.triggerNames(*triggerResultsHandle).triggerNames();
    std::set<std::string> modules;
    for ( int i=0, n=triggerNames.size(); i<n; ++i ) {
      if ( !triggerResultsHandle->accept(i) ) continue;
      const auto& stmodules = hltConfig_.saveTagsModules(i);

      for ( size_t j=0, m=triggerPaths_.size(); j<m; ++j ) {
        const auto path = triggerPaths_[j];
        const auto module = (j < triggerModules_.size()) ? triggerModules_[j] : "";

        if ( hltConfig_.removeVersion(triggerNames[i]) != path ) continue;

        // Keep module names 
        if ( module.empty() ) modules.insert(stmodules.begin(), stmodules.end()); // all modules if not specified
        else if ( std::find(stmodules.begin(), stmodules.end(), module) != stmodules.end() ) modules.insert(module);
      }
    }

    std::vector<math::XYZTLorentzVector> triggerObjectP4s;
    
    const auto& triggerObjects = triggerEventHandle->getObjects();
    for ( size_t keyIdx = 0; keyIdx < triggerEventHandle->sizeFilters(); ++keyIdx ) {
      const auto filterLabelView = triggerEventHandle->filterLabel(keyIdx);
      const std::string filterLabelString(filterLabelView.begin(), filterLabelView.end());
      if ( modules.count(filterLabelString) == 0 ) continue;

      for ( auto objIdx : triggerEventHandle->filterKeys(keyIdx) ) {
        //if ( std::abs(triggerObjects[objIdx].id()) != 13 ) continue;
        triggerObjectP4s.push_back(triggerObjects[objIdx].particle().p4());
      }
    }
    if ( triggerObjectP4s.empty() ) break;

    // Select best tag muon
    for ( int i=0, n=muonHandle->size(); i<n; ++i ) {
      const auto& mu = muonHandle->at(i);
      const double pt = mu.pt();

      // Basic kinematic cuts
      if ( pt < minMuonPt_ or std::abs(mu.eta()) > maxMuonAbsEta_ ) continue;

      // Tight muon ID
      if ( mu.track().isNull() ) continue;
      if      ( tagIdType_ == IDType::Tight   and !muon::isTightMuon(mu, pv) ) continue;
      else if ( tagIdType_ == IDType::Soft    and !muon::isSoftMuon(mu, pv) ) continue;
      else if ( tagIdType_ == IDType::Tracker and !(mu.isTrackerMuon() and muon::isGoodMuon(mu, muon::TMOneStationLoose)) ) continue;
      else if ( tagIdType_ == IDType::RPC     and !(mu.isRPCMuon() and muon::isGoodMuon(mu, muon::RPCMuLoose)) ) continue;

      // Tight muon isolation
      const double chIso = mu.pfIsolationR03().sumChargedHadronPt;
      const double nhIso = mu.pfIsolationR03().sumNeutralHadronEt;
      const double phIso = mu.pfIsolationR03().sumPhotonEt;
      const double puIso = mu.pfIsolationR03().sumPUPt;
      if ( chIso + std::max(0., nhIso+phIso-0.5*puIso) > pt*maxMuonRelIso_ ) continue;

      // Trigger matching
      const bool isTrigMatching = [&](){
        for ( const auto& to : triggerObjectP4s ) {
          if ( deltaR(mu, to) < 0.1 and std::abs(mu.pt()-to.pt()) < 0.5*mu.pt() ) return true;
        }
        return false; }();
      if ( !isTrigMatching ) break;

      if ( tagRef.isNull() or tagRef->pt() < pt ) tagRef = reco::MuonRef(muonHandle, i);
    }
    if ( tagRef.isNull() ) break;

    // Find best tag + probe pair
    for ( int i=0, n=muonHandle->size(); i<n; ++i ) {
      const auto& mu = muonHandle->at(i);
      if ( idType_ == IDType::Tracker ) {
        if ( !mu.isTrackerMuon() ) continue;
        if ( !muon::isGoodMuon(mu, muon::TMOneStationLoose) ) continue;
      }
      else if ( idType_ == IDType::RPC ) {
        if ( !mu.isRPCMuon() ) continue;
        if ( !muon::isGoodMuon(mu, muon::RPCMuLoose) ) continue;
      }
      else if ( idType_ == IDType::Tight ) {
        if ( !muon::isTightMuon(mu, pv) ) continue;
      }
      else if ( idType_ == IDType::Soft ) {
        if ( !muon::isSoftMuon(mu, pv) ) continue;
      }
      if ( mu.track()->originalAlgo() == reco::TrackBase::muonSeededStepOutIn ) continue;

      const double pt = mu.pt();

      // Basic kinematic cuts
      if ( pt < minTrackPt_ or std::abs(mu.eta()) > maxTrackAbsEta_ ) continue;

      // Require opposite charge and do overlap check
      if ( doCheckSign_ and mu.charge() == tagRef->charge() ) continue;
      if ( deltaR(mu, tagRef->p4()) < minDR_ ) continue;

      // Set four momentum with muon hypothesis, compute invariant mass
      const double m = (tagRef->p4()+mu.p4()).mass();
      if ( m < minMass_ or m > maxMass_ ) continue;

      if ( probeRef.isNull() or probeRef->pt() < pt ) {
        probeRef = reco::MuonRef(muonHandle, i);
        mass = m;
      }
    }
    if ( probeRef.isNull() ) break;

    // Now we have tag + probe pair, mass is already set to 'mass' variable
    // Next step is to find detectors where the probe track is expected to pass through
  } while ( false );

  if ( tagRef.isNonnull() ) out_tag->push_back(*tagRef);
  if ( probeRef.isNonnull() ) out_probe->push_back(*probeRef);

  event.put(std::move(out_probe));
  event.put(std::move(out_tag), "tag");
  event.put(std::make_unique<double>(mass), "mass");
}

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(RPCTrackerMuonProbeProducer);

