import { ChatAPI } from '../services/api';
import { usePolling } from './usePolling';
import type { Task } from '../types';

export function useTasks(intervalMs = 10_000) {
  const state = usePolling<{ tasks: Task[] }>(() => ChatAPI.fetchTasks(), intervalMs);

  async function createTask(description: string, assignee?: string) {
    await ChatAPI.createTask(description, assignee);
    await state.refresh();
  }

  return { ...state, tasks: state.data?.tasks ?? [], createTask };
}
