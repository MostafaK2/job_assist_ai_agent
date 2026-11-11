"use client";

import Link from "next/link";
import { useState } from "react";
import DetailsForm from "@/components/onboarding/DetailsForm";
import EmploymentInformationForm from "@/components/onboarding/EmploymentInformationForm";
import PreferencesForm from "@/components/onboarding/PreferencesForm";
import ResumeUpload from "@/components/onboarding/ResumeUpload";
import StepIndicator from "@/components/onboarding/StepIndicator";
import { DEFAULT_EMPLOYMENT, DEFAULT_PREFERENCES, DEFAULT_SETTINGS, saveProfile } from "@/lib/onboarding";

// Steps, in order. Keep in sync with StepIndicator's labels.
const UPLOAD = 0;
const DETAILS = 1;
const EMPLOYMENT = 2;
const PREFERENCES = 3;
const DONE = 4;

export default function OnboardingFlow() {
  const [step, setStep] = useState(UPLOAD);
  const [uploadId, setUploadId] = useState(null);
  const [resume, setResume] = useState(null);
  const [employment, setEmployment] = useState(DEFAULT_EMPLOYMENT);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  function handleUploaded({ uploadId, resume }) {
    setUploadId(uploadId);
    setResume(resume);
    // Start with the roles suggested from the resume already selected.
    setPreferences((p) => ({ ...p, target_roles: resume.suggested_roles.slice(0, 2) }));
    setStep(DETAILS);
  }

  async function handleSave(prefs, reviewSettings) {
    setPreferences(prefs);
    setSettings(reviewSettings);
    setSaving(true);
    setSaveError(null);
    try {
      await saveProfile({ uploadId, resume, employment, preferences: prefs, settings: reviewSettings });
      setStep(DONE);
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  if (step === DONE) {
      const first = resume.preferred_name?.trim() || resume.first_name || "there";    
      return (
      <div className="rounded-xl border border-line bg-surface p-8">
        <h2 className="text-2xl font-bold">You&apos;re all set, {first}.</h2>
        <p className="mt-2 text-muted">
          Your profile is saved. Looking for {preferences.target_roles.join(", ")} roles.
        </p>
        <Link href="/chat" className="mt-6 inline-block rounded-md bg-ink px-5 py-2.5 font-medium text-white">
          Start searching
        </Link>
      </div>
    );
  }

  return (
    <>
      <StepIndicator current={step} />

      {step === UPLOAD && <ResumeUpload onDone={handleUploaded} />}

      {step === DETAILS && (
        <DetailsForm
          resume={resume}
          onBack={() => setStep(UPLOAD)}
          onDone={(details) => { setResume(details); setStep(EMPLOYMENT); }}
        />
      )}

      {step === EMPLOYMENT && (
        <EmploymentInformationForm
          initial={employment}
          onBack={() => setStep(DETAILS)}
          onDone={(info) => { setEmployment(info); setStep(PREFERENCES); }}
        />
      )}

      {step === PREFERENCES && (
        <PreferencesForm
          suggestedRoles={resume.suggested_roles}
          initial={preferences}
          initialSettings={settings}
          saving={saving}
          error={saveError}
          onBack={() => setStep(EMPLOYMENT)}
          onDone={handleSave}
        />
      )}
    </>
  );
}