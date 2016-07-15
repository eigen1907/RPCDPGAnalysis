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

#include "DataFormats/RPCRecHit/interface/RPCRecHit.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitCollection.h"
#include "DataFormats/MuonDetId/interface/RPCDetId.h"

#include "TrackingTools/TrackAssociator/interface/TrackDetectorAssociator.h"
#include "TrackingTools/Records/interface/TrackingComponentsRecord.h"

#include "DataFormats/Math/interface/deltaR.h"

#include <vector>
#include <string>
#include <memory>
#include <cmath>

class RPCPointFromTagProbeProducer : public edm::stream::EDProducer<>
{
public:
  RPCPointFromTagProbeProducer(const edm::ParameterSet& pset);
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
  const double minMass_, maxMass_;
  const std::vector<std::string> triggerPaths_;

  const std::string propagatorName_;
  const TrackAssociatorParameters taParams_;

  HLTConfigProvider hltConfig_;
};

RPCPointFromTagProbeProducer::RPCPointFromTagProbeProducer(const edm::ParameterSet& pset):
  triggerResultsToken_(consumes<edm::TriggerResults>(pset.getParameter<edm::InputTag>("triggerResults"))),
  pvToken_(consumes<reco::VertexCollection>(pset.getParameter<edm::InputTag>("vertex"))),
  muonToken_(consumes<reco::MuonCollection>(pset.getParameter<edm::InputTag>("muons"))),
  triggerEventToken_(consumes<trigger::TriggerEvent>(pset.getParameter<edm::InputTag>("triggerObjects"))),
  minMuonPt_(pset.getParameter<double>("minMuonPt")),
  maxMuonAbsEta_(pset.getParameter<double>("maxMuonAbsEta")),
  maxMuonRelIso_(pset.getParameter<double>("maxMuonRelIso")),
  minTrackPt_(pset.getParameter<double>("minTrackPt")),
  maxTrackAbsEta_(pset.getParameter<double>("maxTrackAbsEta")),
  minMass_(pset.getParameter<double>("minMass")),
  maxMass_(pset.getParameter<double>("maxMass")),
  triggerPaths_(pset.getParameter<std::vector<std::string>>("triggerPaths")),
  propagatorName_(pset.getParameter<std::string>("propagatorName")),
  taParams_(pset.getParameter<edm::ParameterSet>("TrackAssociatorParameters"), consumesCollector())
{
  produces<RPCRecHitCollection>();
  produces<double>();
}

void RPCPointFromTagProbeProducer::beginRun(const edm::Run& run, const  edm::EventSetup& eventSetup)
{
  bool changed = true;
  hltConfig_.init(run, eventSetup, "HLT", changed);
}

void RPCPointFromTagProbeProducer::produce(edm::Event& event, const edm::EventSetup& eventSetup)
{
  using namespace std;

  std::auto_ptr<RPCRecHitCollection> out_points(new RPCRecHitCollection);
  double mass = -1;

  edm::Handle<edm::TriggerResults> triggerResultsHandle;
  event.getByToken(triggerResultsToken_, triggerResultsHandle);

  edm::Handle<reco::VertexCollection> pvHandle;
  event.getByToken(pvToken_, pvHandle);

  edm::Handle<reco::MuonCollection> muonHandle;
  event.getByToken(muonToken_, muonHandle);

  edm::Handle<trigger::TriggerEvent> triggerEventHandle;
  event.getByToken(triggerEventToken_, triggerEventHandle);

  edm::ESHandle<Propagator> propagator;
  eventSetup.get<TrackingComponentsRecord>().get(propagatorName_, propagator);
  TrackDetectorAssociator trackAssociator;
  trackAssociator.setPropagator(propagator.product());

  do {
    if ( pvHandle->empty() ) break;
    const auto pv = pvHandle->at(0);

    // Collect interested trigger objects
    auto triggerNames = event.triggerNames(*triggerResultsHandle).triggerNames();
    std::set<std::string> modules;
    for ( int i=0, n=triggerNames.size(); i<n; ++i ) {
      if ( !triggerResultsHandle->accept(i) ) continue;
      for ( const auto path : triggerPaths_ ) {
        if ( hltConfig_.removeVersion(triggerNames[i]) != path ) continue;

        const auto& stmodules = hltConfig_.saveTagsModules(i);
        modules.insert(stmodules.begin(), stmodules.end());
      }
    }

    std::vector<math::XYZTLorentzVector> triggerObjectP4s;
    const auto& triggerObjects = triggerEventHandle->getObjects();
    for ( size_t keyIdx = 0; keyIdx < triggerEventHandle->sizeFilters(); ++keyIdx ) {
      if ( modules.count(triggerEventHandle->filterLabel(keyIdx)) == 0 ) continue;

      for ( auto objIdx : triggerEventHandle->filterKeys(keyIdx) ) {
        triggerObjectP4s.push_back(triggerObjects[objIdx].particle().p4());
      }
    }
    if ( triggerObjectP4s.empty() ) break;

    // Select best tag muon
    reco::MuonRef tagRef;
    for ( int i=0, n=muonHandle->size(); i<n; ++i ) {
      const auto& mu = muonHandle->at(i);
      const double pt = mu.pt();

      // Basic kinematic cuts
      if ( pt < minMuonPt_ or std::abs(mu.eta()) > maxMuonAbsEta_ ) continue;

      // Tight muon ID
      if ( mu.track().isNull() ) continue;
      if ( !muon::isTightMuon(mu, pv) ) continue;

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
    reco::MuonRef probeRef;
    for ( int i=0, n=muonHandle->size(); i<n; ++i ) {
      const auto& mu = muonHandle->at(i);
      if ( !mu.isTrackerMuon() ) continue;
      if ( !muon::isGoodMuon(mu, muon::TMOneStationLoose) ) continue;

      const double pt = mu.pt();

      // Basic kinematic cuts
      if ( pt < minTrackPt_ or std::abs(mu.eta()) > maxTrackAbsEta_ ) continue;

      // Require opposite charge. Overlap check is done automatically
      if ( mu.charge() == tagRef->charge() ) continue;

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
    edm::OwnVector<RPCRecHit> pointVector;
    for ( auto ch : probeRef->matches() ) {
      if ( ch.detector() != 3 ) continue;
      //auto rpcMatch = muMatch.rpcMatches;

      const LocalError lErr(ch.xErr, ch.yErr, 0);
      const LocalPoint lPos(ch.x, ch.y, 0);

      pointVector.clear();
      pointVector.push_back(RPCRecHit(ch.id, 0, lPos, lErr));
      out_points->put(ch.id, pointVector.begin(), pointVector.end());
    }

  } while ( false );

  event.put(out_points);
  event.put(std::auto_ptr<double>(new double(mass)));
}

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(RPCPointFromTagProbeProducer);

