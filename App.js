import React, { useEffect, useState, useRef } from 'react';
import './components/styles.css';
import { db, auth } from './firebaseConfig';
import {
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
} from 'firebase/auth';
import {
  doc,
  onSnapshot,
  setDoc,
  collection,
  addDoc,
  serverTimestamp,
  query,
  where,
  orderBy,
  limit,
  getDoc,
} from 'firebase/firestore';
import VehicleRegistrationForm from './components/VehicleRegistrationForm';

const DEFAULT_DRIVER_ID =
  typeof process !== 'undefined'
    ? process.env.REACT_APP_DRIVER_ID || 'SR-72EE6B-I3MQI'
    : 'SR-72EE6B-I3MQI';

const speak = (text) => {
  if (!('speechSynthesis' in window)) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 1;
  utter.pitch = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
};

const formatNumber = (v, decimals = 3) =>
  typeof v === 'number' ? v.toFixed(decimals) : 'N/A';

// ---- AuthGate: blocks UI until user completes Google Sign-In ----
function AuthGate({ children }) {
  const [authReady, setAuthReady] = React.useState(false);
  const [user, setUser] = React.useState(null);

  React.useEffect(() => {
    const unsub = onAuthStateChanged(auth, (u) => {
      setUser(u || null);
      setAuthReady(true);
    });
    return () => unsub();
  }, []);

  const handleGoogle = async () => {
    try {
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: 'select_account' });
      await signInWithPopup(auth, provider);
    } catch (err) {
      console.error('Google sign-in failed:', err);
      alert('Google sign-in failed. Please try again.');
    }
  };

  if (!authReady) {
    return (
      <div style={{ textAlign: 'center', marginTop: '20%' }}>
        <h3>Loading SafeRide…</h3>
      </div>
    );
  }

  if (!user || !user.providerData.some((p) => p.providerId === 'google.com')) {
    return (
      <div style={{ textAlign: 'center', marginTop: '15%' }}>
        <h2>Welcome to SafeRide</h2>
        <p>Please sign in with Google to continue.</p>
        <button
          onClick={handleGoogle}
          style={{
            padding: '10px 20px',
            fontSize: '16px',
            background: '#4285F4',
            color: '#fff',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer',
          }}
        >
          Sign in with Google
        </button>
      </div>
    );
  }

  return <>{children}</>;
}

export default function App() {
  const [driverId, setDriverId] = useState(DEFAULT_DRIVER_ID);
  const [inputId, setInputId] = useState(DEFAULT_DRIVER_ID);
  const [showRegistration, setShowRegistration] = useState(false);

  // Live monitoring state
  const [status, setStatus] = useState('No Data');
  const [ear, setEar] = useState(0);
  const [mar, setMar] = useState(0);
  const [pitch, setPitch] = useState(0);
  const [yaw, setYaw] = useState(0);
  const [speed, setSpeed] = useState(0);
  const [overallRisk, setOverallRisk] = useState(0);
  const [hasAccident, setHasAccident] = useState(false);
  const [loading, setLoading] = useState(true);

  // Emergency overlay
  const [isEmergencyPromptVisible, setIsEmergencyPromptVisible] = useState(false);
  const [countdown, setCountdown] = useState(3);
  const countdownRef = useRef(null);
  const responseHandledRef = useRef(false);
  const criticalStartRef = useRef(null);
  const emergencyTriggeredRef = useRef(false);
  const emergencyIntervalRef = useRef(null);
  const retryYesTimeoutRef = useRef(null);
  const alarmRef = useRef(null);
  const CRITICAL_THRESHOLD_SECONDS = 6;

  // NEW: After pressing "No", lock out future prompts until reset/switch ID.
  const helpAcknowledgedRef = useRef(false);
  // NEW: After pressing "Yes", suppress prompts until status returns to normal.
  const yesAcknowledgedRef = useRef(false);

  // Reset Request state
  const [resetStatus, setResetStatus] = useState(null);
  const [resetReason, setResetReason] = useState(null);

  useEffect(() => {
    try {
      alarmRef.current = new Audio('/alarm.wav');
      alarmRef.current.loop = true;
    } catch (e) {
      alarmRef.current = null;
    }
  }, []);

  // Auth debug
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (user) => {
      if (!user) console.log('User not signed in. Waiting for Google login…');
      else console.log('Signed in with Google:', user.email);
    });
    return () => unsub();
  }, []);

  // Registration listener
  useEffect(() => {
    if (!db || !driverId) return;
    const vehicleRef = doc(db, 'registeredVehicles', driverId);
    const unsub = onSnapshot(vehicleRef, (snap) => {
      if (!snap.exists() || !snap.data().registrationComplete) {
        setShowRegistration(true);
      } else {
        const vehicleData = snap.data();
        const currentUser = auth.currentUser;
        if (vehicleData.ownerEmail && currentUser?.email !== vehicleData.ownerEmail) {
          alert('This vehicle is registered to another driver. Please request a reset.');
          setShowRegistration(false);
          return;
        }
        setShowRegistration(false);
      }
    });
    return () => unsub();
  }, [db, driverId]);

  // Driver status listener
  useEffect(() => {
    if (!db || !driverId) return;
    setLoading(true);
    const docRef = doc(db, 'driver_status', driverId);

    let isFirstSnapshot = true; // <<< ADD THIS FLAG

    const unsub = onSnapshot(docRef, (snap) => {
      if (!snap.exists()) {
        setStatus('No Data');
        setEar(0);
        setMar(0);
        setPitch(0);
        setYaw(0);
        setSpeed(0);
        setOverallRisk(0);
        setHasAccident(false);
        setLoading(false);
        stopAlarmAndPrompt();
        return;
      }

      const data = snap.data();
      const statusText = (data.status || 'normal').toLowerCase();

      // Reset yes-acknowledgement when driver returns to normal
      if (statusText === 'normal') {
        yesAcknowledgedRef.current = false;
      }

      setStatus(data.status || 'Unknown');
      setEar(data.ear ?? 0);
      setMar(data.mar ?? 0);
      setPitch(data.pitch ?? 0);
      setYaw(data.yaw ?? 0);
      setSpeed(data.speed ?? 0);
      setOverallRisk(data.overall_risk_score ?? 0);
      setHasAccident(!!data.hasAccident);
      setLoading(false);

      const isHigh = statusText.includes('high') || statusText.includes('severe');
      const isCritical = statusText.includes('critical') || !!data.hasAccident;

      if (isFirstSnapshot) {
        // Do NOT trigger emergency on first load
        isFirstSnapshot = false;
        return;
      }

      // 🚫 If driver already pressed "No", never prompt again (until ID changes / reset)
      if (helpAcknowledgedRef.current) {
        return;
      }

      // 🚫 If driver pressed "Yes" previously, suppress prompts until they return to NORMAL
      if (yesAcknowledgedRef.current && statusText !== 'normal') {
        return;
      }

      if (isHigh && !responseHandledRef.current) {
        handleEmergencyPrompt('high');
      } else if (isCritical) {
        handleEmergencyPrompt('critical');
      } else {
        stopAlarmAndPrompt();
        criticalStartRef.current = null;
      }
    });

    return () => unsub();
  }, [db, driverId]);

  // 🔹 Send Reset Request
  const handleRequestReset = async () => {
    try {
      const user = auth.currentUser;
      if (!user) {
        alert('You must be signed in to request a reset.');
        return;
      }
      await addDoc(collection(db, 'reset_requests'), {
        driver_id: driverId,
        email: user.email,
        status: 'pending',
        createdAt: serverTimestamp(),
      });
      setResetStatus('pending');
      alert('Reset request sent ✅');
    } catch (err) {
      console.error('Failed to send reset request:', err);
      alert('Error sending reset request ❌');
    }
  };

  // 🔹 Listen for reset request updates
  useEffect(() => {
    if (!auth.currentUser) return;
    const q = query(
      collection(db, 'reset_requests'),
      where('driver_id', '==', driverId),
      where('email', '==', auth.currentUser.email),
      orderBy('createdAt', 'desc'),
      limit(1)
    );
    const unsub = onSnapshot(q, (snapshot) => {
      if (snapshot.empty) {
        setResetStatus(null);
        setResetReason(null);
        return;
      }
      const req = snapshot.docs[0].data();
      setResetStatus(req.status);
      setResetReason(req.reason || req.note || req.newVehicleId || null);

      if (req.status === 'approved') {
        setShowRegistration(true);
        setStatus('No Data');
        setEar(0);
        setMar(0);
        setPitch(0);
        setYaw(0);
        setSpeed(0);
        setOverallRisk(0);
        setHasAccident(false);
      }

      if (req.status === 'done' && req.newVehicleId) {
        setDriverId(req.newVehicleId);
        setInputId(req.newVehicleId);
        setShowRegistration(true);
        // When switching to a new ID, allow prompts again
        helpAcknowledgedRef.current = false;
        yesAcknowledgedRef.current = false;
      }
    });
    return () => unsub();
  }, [driverId]);

  // ---------------- Emergency Handling ----------------
  const handleEmergencyPrompt = (level) => {
    // Respect "No" or "Yes" locks: never show prompt again if acknowledged
    if (helpAcknowledgedRef.current || yesAcknowledgedRef.current) return;

    if (!isEmergencyPromptVisible) {
      responseHandledRef.current = false;
      setCountdown(3);
      setIsEmergencyPromptVisible(true);

      const message =
        level === 'high'
          ? 'Your status is high. Are you okay? Press Yes if fine, No if you need help.'
          : 'Critical alert! Are you okay? Press Yes if fine, No if you need help.';

      speak(message);
      startCountdown();

      if (level === 'critical') {
        if (!emergencyIntervalRef.current) {
          emergencyIntervalRef.current = setInterval(() => {
            if (!responseHandledRef.current) triggerEmergencyCall('critical_repeat');
            else {
              clearInterval(emergencyIntervalRef.current);
              emergencyIntervalRef.current = null;
            }
          }, 3000);
        }
      }
    }
  };

  const startCountdown = () => {
    stopCountdown();
    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(countdownRef.current);
          countdownRef.current = null;
          if (!responseHandledRef.current) onNoResponse();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const stopCountdown = () => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  };

  const stopAlarmAndPrompt = () => {
    if (alarmRef.current) {
      alarmRef.current.pause();
      alarmRef.current.currentTime = 0;
    }
    setIsEmergencyPromptVisible(false);
    stopCountdown();

    if (emergencyIntervalRef.current) {
      clearInterval(emergencyIntervalRef.current);
      emergencyIntervalRef.current = null;
    }

    if (retryYesTimeoutRef.current) {
      clearTimeout(retryYesTimeoutRef.current);
      retryYesTimeoutRef.current = null;
    }

    emergencyTriggeredRef.current = false;
    responseHandledRef.current = false;
    // NOTE: do NOT reset helpAcknowledgedRef here; "No" should keep blocking prompts
    // NOTE: do NOT reset yesAcknowledgedRef here — it must persist until status returns to normal
  };

  const onYes = async () => {
    if (responseHandledRef.current) return;
    responseHandledRef.current = true;
    stopAlarmAndPrompt();
    speak('Okay. Please park safely if you are feeling unwell.');

    // Mark local suppression and write to Firestore so backend also suppresses
    yesAcknowledgedRef.current = true;

    try {
      await setDoc(
        doc(db, 'driver_responses', driverId),
        {
          response: 'yes',
          createdAt: serverTimestamp(),
          driverId,
          email: auth.currentUser?.email || null,
        },
        { merge: true }
      );
    } catch (e) {
      console.error('Failed to write driver response (yes):', e);
    }

    // We intentionally do NOT schedule a re-check here.
    // The driver_remains_suppressed until their driver_status becomes "Normal".
  };

  const onNo = async () => {
    if (responseHandledRef.current) return;
    responseHandledRef.current = true;

    // Lock future prompts for this session/vehicle until reset
    helpAcknowledgedRef.current = true;

    stopAlarmAndPrompt();
    speak('Thanks for your feedback. Help is on the way.');

    // Optionally record response 'no' (not required for backend, but harmless)
    try {
      await setDoc(
        doc(db, 'driver_responses', driverId),
        {
          response: 'no',
          createdAt: serverTimestamp(),
          driverId,
          email: auth.currentUser?.email || null,
        },
        { merge: true }
      );
    } catch (e) {
      // ignore write errors
    }

    await triggerEmergencyCall('driver_pressed_no');
  };

  const onNoResponse = async () => {
    if (responseHandledRef.current) return;
    responseHandledRef.current = true;
    stopAlarmAndPrompt();
    await triggerEmergencyCall('no_response_timeout');
  };

  const triggerEmergencyCall = async (reason) => {
    if (emergencyTriggeredRef.current) return;
    emergencyTriggeredRef.current = true;

    if (alarmRef.current && alarmRef.current.paused) {
      alarmRef.current.play().catch(() => {});
    }

    try {
      await addDoc(collection(db, 'emergency_calls'), {
        driver_id: driverId,
        reason,
        createdAt: serverTimestamp(),
        handled: false,
      });

      await setDoc(
        doc(db, 'driver_status', driverId),
        {
          emergencyCalled: true,
          emergencyReason: reason,
          emergencyTimestamp: serverTimestamp(),
        },
        { merge: true }
      );
    } catch (err) {
      console.error(err);
    }

    speak('Emergency unit notified. Help is on the way.');
  };

  // ---------------- Utility ----------------
  const metricClass = (value, lowThreshold, highThreshold) => {
    if (value >= highThreshold) return 'metric-red';
    if (value >= lowThreshold) return 'metric-yellow';
    return 'metric-green';
  };

  const handleSetMonitor = () => {
    setDriverId(inputId.trim() || DEFAULT_DRIVER_ID);
    // When switching vehicles, re-allow prompts
    helpAcknowledgedRef.current = false;
    yesAcknowledgedRef.current = false;
  };

  // ---------------- Render ----------------
  return (
    <AuthGate>
      <div className="dm-root">
        {/* Header */}
        <header className="dm-top">
          <div className="dm-top-left">
            <div className="dm-brand">
              <div className="dm-brand-icon">🚗</div>
              <div>
                <h1>Saferide Driver Monitor</h1>
                <div className="dm-sub">
                  Vehicle: <span className="dm-mono">{driverId}</span>
                </div>
              </div>
            </div>
          </div>
          <div className="dm-top-right">
            <div className="dm-id-input">
              <input value={inputId} onChange={(e) => setInputId(e.target.value)} />
              <button onClick={handleSetMonitor}>Monitor</button>
            </div>
            <button onClick={() => signOut(auth)} style={{ marginLeft: '10px' }}>
              Logout
            </button>
          </div>
        </header>

        {/* Main */}
        <main className="dm-main">
          {showRegistration ? (
            <VehicleRegistrationForm
              driverId={driverId}
              onRegisterSuccess={async () => {
                await setDoc(
                  doc(db, 'registeredVehicles', driverId),
                  { ownerEmail: auth.currentUser.email, registrationComplete: true },
                  { merge: true }
                );
                setShowRegistration(false);
              }}
            />
          ) : (
            <>
              {/* Cards */}
              <section className="dm-cards">
                <div
                  className={`dm-card status-card ${
                    status.toLowerCase().includes('critical') ? 'critical' : ''
                  }`}
                >
                  <div className="dm-card-title">Overall Status</div>
                  <div className="dm-card-value">{loading ? 'Loading…' : status}</div>
                  {hasAccident && <div className="dm-card-note">Accident detected</div>}
                </div>

                <div className={`dm-card ${metricClass(ear, 0.18, 0.23)}`}>
                  <div className="dm-card-title">Eye Aspect Ratio (EAR)</div>
                  <div className="dm-card-value">{formatNumber(ear, 3)}</div>
                  <div className="dm-card-note">Lower is worse</div>
                </div>

                <div className={`dm-card ${metricClass(mar, 0.3, 0.6)}`}>
                  <div className="dm-card-title">Mouth Aspect Ratio (MAR)</div>
                  <div className="dm-card-value">{formatNumber(mar, 3)}</div>
                  <div className="dm-card-note">Higher is worse</div>
                </div>

                <div className={`dm-card ${metricClass(Math.abs(pitch), 10, 20)}`}>
                  <div className="dm-card-title">Pitch (°)</div>
                  <div className="dm-card-value">{formatNumber(pitch, 1)}°</div>
                  <div className="dm-card-note">Head nods</div>
                </div>

                <div className={`dm-card ${metricClass(Math.abs(yaw), 15, 30)}`}>
                  <div className="dm-card-title">Yaw (°)</div>
                  <div className="dm-card-value">{formatNumber(yaw, 1)}°</div>
                  <div className="dm-card-note">Head turns</div>
                </div>

                <div className={`dm-card ${metricClass(overallRisk, 0.4, 0.75)}`}>
                  <div className="dm-card-title">Distraction Index</div>
                  <div className="dm-card-value">{formatNumber(overallRisk, 2)}</div>
                  <div className="dm-card-note">Higher is worse</div>
                </div>

                <div className="dm-card">
                  <div className="dm-card-title">Speed (KM/H)</div>
                  <div className="dm-card-value">{speed}</div>
                  <div className="dm-card-note">Current vehicle speed</div>
                </div>
              </section>

              {/* Reset Section */}
              <section className="dm-reset" style={{ marginTop: '20px' }}>
                <h3>Need to reset your SafeRide ID?</h3>
                {resetStatus === 'pending' && (
                  <p>⏳ Reset request sent. Waiting for admin approval…</p>
                )}
                {resetStatus === 'approved' && (
                  <p>
                    ✅ Your reset request was approved. Please wait while SafeRide assigns you a
                    new Vehicle ID…
                  </p>
                )}
                {resetStatus === 'done' && (
                  <p>
                    ✅ Your reset is complete. A new SafeRide ID has been assigned:{' '}
                    <strong>{resetReason || 'Check registration form'}</strong>. Please re-register
                    your vehicle now.
                  </p>
                )}
                {resetStatus === 'rejected' && (
                  <p>
                    ❌ Your reset request was rejected by admin.{' '}
                    {resetReason && <span> Reason: {resetReason}</span>}
                  </p>
                )}
                {resetStatus === null && (
                  <button
                    onClick={handleRequestReset}
                    style={{
                      padding: '10px 20px',
                      marginTop: '10px',
                      background: 'orange',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: 'pointer',
                    }}
                  >
                    Request Reset
                  </button>
                )}
              </section>

              {/* Info */}
              <section className="dm-right">
                <div className="dm-ticker">
                  <div className="dm-ticker-track">
                    <span>
                      ⚠️ Wear your seat belt &nbsp; • &nbsp; Keep both hands on wheel &nbsp; •
                      &nbsp; Don’t use your phone while driving &nbsp; • &nbsp; Take a break when
                      tired
                    </span>
                  </div>
                </div>
                <div className="dm-info">
                  <h3>Live Info</h3>
                  <p>
                    <strong>EAR:</strong> {formatNumber(ear)} &nbsp; <strong>MAR:</strong>{' '}
                    {formatNumber(mar)}
                  </p>
                  <p>
                    <strong>Pitch:</strong> {formatNumber(pitch, 1)}° &nbsp; <strong>Yaw:</strong>{' '}
                    {formatNumber(yaw, 1)}°
                  </p>
                  <p>
                    <strong>Risk:</strong> {formatNumber(overallRisk, 2)} &nbsp; <strong>Speed:</strong>{' '}
                    {speed} km/h
                  </p>
                </div>
              </section>
            </>
          )}
        </main>
        {isEmergencyPromptVisible && (
          <div className="overlay">
            <div className="overlay-content">
              <h2>Are you okay?</h2>
              <p>Sending help in {countdown} seconds…</p>
              <div style={{ marginTop: '20px' }}>
                <button
                  onClick={onYes}
                  style={{
                    padding: '10px 20px',
                    background: 'green',
                    color: 'white',
                    border: 'none',
                    borderRadius: '5px',
                    marginRight: '10px',
                  }}
                >
                  Yes, I’m Okay
                </button>
                <button
                  onClick={onNo}
                  style={{
                    padding: '10px 20px',
                    background: 'red',
                    color: 'white',
                    border: 'none',
                    borderRadius: '5px',
                  }}
                >
                  No, Send Help
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AuthGate>
  );
}
