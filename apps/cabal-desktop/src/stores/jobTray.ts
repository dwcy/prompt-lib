// Zustand store tracking in-flight job ids the shell shows globally (job tray).
import { create } from "zustand";

interface JobTrayState {
  jobIds: string[];
}

interface JobTrayActions {
  addJob: (jobId: string) => void;
  removeJob: (jobId: string) => void;
  clear: () => void;
}

export const useJobTrayStore = create<JobTrayState & JobTrayActions>()((set) => ({
  jobIds: [],
  addJob: (jobId) =>
    set((state) => (state.jobIds.includes(jobId) ? state : { jobIds: [...state.jobIds, jobId] })),
  removeJob: (jobId) => set((state) => ({ jobIds: state.jobIds.filter((id) => id !== jobId) })),
  clear: () => set({ jobIds: [] }),
}));
