// src/components/VehicleRegistrationForm.js
import React, { useState } from 'react';
import { db } from '../firebaseConfig';
import { doc, setDoc, serverTimestamp as firestoreTimestamp } from 'firebase/firestore';

export default function VehicleRegistrationForm({ driverId, onRegisterSuccess }) {
  const [registrationData, setRegistrationData] = useState({
    name: '',
    licensePlate: '',
    vehicleMake: '',
    vehicleModel: '',
    emergencyContact1Name: '',
    emergencyContact1Phone: '',
    emergencyContact2Name: 'National Ambulance Service',
    emergencyContact2Phone: '193',
  });
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    // Simple validation
    if (!registrationData.name || !registrationData.driverName || !registrationData.licensePlate || !registrationData.vehicleMake || !registrationData.vehicleModel || !registrationData.emergencyContact1Name || !registrationData.emergencyContact1Phone) {
      alert('Please fill all required fields');
      return;
    }

    setLoading(true);

    try {
      await setDoc(
        doc(db, 'registeredVehicles', driverId),
        {
          ...registrationData,
          vehicleId: driverId,
          driverId: driverId,
          active: true,
          status: 'Active',
          registrationComplete: true,
          registrationDate: firestoreTimestamp(),
          registeredAt: firestoreTimestamp(),
          lastSeen: firestoreTimestamp(),
        },
        { merge: true }
      );

      if (onRegisterSuccess) onRegisterSuccess();
    } catch (err) {
      console.error('Registration failed:', err);
      alert('Registration failed. Check console for details.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="registration-form">
      <h2>Register Your Vehicle</h2>
      <input
        placeholder="Full Name"
        value={registrationData.name}
        onChange={(e) => setRegistrationData({ ...registrationData, name: e.target.value })}
      />
      <input
        placeholder="Driver Name"
        value={registrationData.driverName}
        onChange={(e) => setRegistrationData({ ...registrationData, driverName: e.target.value })}
      />
      <input
        placeholder="License Plate"
        value={registrationData.licensePlate}
        onChange={(e) => setRegistrationData({ ...registrationData, licensePlate: e.target.value })}
      />
      <input
        placeholder="Vehicle Make"
        value={registrationData.vehicleMake}
        onChange={(e) => setRegistrationData({ ...registrationData, vehicleMake: e.target.value })}
      />
      <input
        placeholder="Vehicle Model"
        value={registrationData.vehicleModel}
        onChange={(e) => setRegistrationData({ ...registrationData, vehicleModel: e.target.value })}
      />
      <input
        placeholder="Emergency Contact 1 Name"
        value={registrationData.emergencyContact1Name}
        onChange={(e) => setRegistrationData({ ...registrationData, emergencyContact1Name: e.target.value })}
      />
      <input
        placeholder="Emergency Contact 1 Phone"
        value={registrationData.emergencyContact1Phone}
        onChange={(e) => setRegistrationData({ ...registrationData, emergencyContact1Phone: e.target.value })}
      />
      {/* Emergency Contact 2 is pre-filled */}
      <input
        placeholder="Emergency Contact 2 Name"
        value={registrationData.emergencyContact2Name}
        disabled
      />
      <input
        placeholder="Emergency Contact 2 Phone"
        value={registrationData.emergencyContact2Phone}
        disabled
      />
      <button onClick={handleRegister} disabled={loading}>
        {loading ? 'Registering...' : 'Register & Start Monitoring'}
      </button>
    </div>
  );
}
