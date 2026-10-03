import { createContext } from "react";
import type { CurrentUser } from "./types";

export type AuthContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);