export type DemoEmail = "patient@demo.az";

export interface DemoUser { id: string; name: string; email: string; role: "PATIENT" }
export interface Patient {
  id: string; name: string; email: string; dob: string; gender: string; phone: string;
  blood_type: string; emergency_contact: string; insurance_plan: string;
  allergies_json: string; conditions_json: string; medications_json: string;
}
export interface Overview {
  patient: { id: string; name: string; insurance_plan: string; allergies: NamedItem[]; conditions: string[]; medications: NamedItem[] };
  upcoming_appointment: Appointment | null; recent_activity: TimelineRecord[]; insight_count: number;
}
export interface NamedItem { name: string; dosage?: string; reaction?: string; recorded?: string }
export interface TimelineRecord { id?: string; type: string; title: string; record_date: string; category: string; raw_text?: string; content_json?: string }
export interface LabPoint { value: number; result_date: string; unit: string }
export interface Trend { metric: string; current: number; previous: number | null; change: number; percent_change: number | null; trend: string; history: LabPoint[] }
export interface TrendsResponse { trends: Trend[]; conflicts: { message: string }[]; care_navigation: { suggested_specialty: string; reason: string } }
export interface LabResult { id: string; metric: string; value: number; unit: string; reference_range: string; result_date: string; record_id: string }
export interface Doctor {
  id: string; name: string; specialty: string; hospital_id: string; hospital_name: string;
  city?: string; experience_years: number; rating: number; price: number; accepted_plans: string | string[];
  availability?: Slot[];
}
export interface Slot { id: string; doctor_id: string; starts_at: string; ends_at: string; status: string }
export interface Appointment {
  id: string; patient_id: string; doctor_id: string; slot_id: string; status: string; reason?: string;
  doctor_name?: string; specialty?: string; hospital_name?: string; starts_at: string; cost_json?: string;
}
export interface Queue { queue_position: number; patients_before: number; estimated_wait_minutes: number }
export interface InsuranceEstimate { plan: string; plan_name: string; service: string; service_price: number; coverage_percent: number; insurance_payment: number; patient_payment: number }
export interface Consent { id: string; doctor_id: string; doctor_name: string; categories_json: string; starts_at: string; expires_at: string; status: string }
export interface Notification { id: string; type: string; message: string; related_type?: string; related_id?: string; read_at?: string; created_at: string }
export interface MedicalDocument { id: string; filename: string; document_type: string; processing_status: string; created_at: string; confirmed_at?: string; extraction_json?: string }
export interface ExtractedLab { test_name: string; value: number; unit: string; reference_text: string; confidence?: number }
export interface Extraction { results: ExtractedLab[]; report_date?: string; source_name?: string; document_type?: string; confidence?: number }
export interface DocumentUpload { document_id: string; status: string; extraction: Extraction }
export interface Checkin { id: string; checkin_date: string; pain_score: number; temperature: number; medication_taken: number; symptoms: string; notes: string }
export interface AIExplanation { data: Trend; ai: { source: string; fallback_used: boolean; content: { title: string; explanation: string; suggested_action: string } } }
