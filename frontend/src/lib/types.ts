export type UserRole = "customer" | "worker" | "admin";
export type WorkerAvailability = "available" | "busy" | "offline";
export type OrderStatus =
  | "pending"
  | "assigned"
  | "accepted"
  | "in_progress"
  | "completion_requested"
  | "completed"
  | "reviewed"
  | "disputed"
  | "canceled";

export interface User {
  id: string;
  role: UserRole;
  full_name: string;
  phone: string | null;
  email: string | null;
  avatar_url: string | null;
  identity_status: string;
  is_active: boolean;
  created_at: string;
}

export interface Worker {
  id: string;
  role: "worker";
  full_name: string;
  phone: string | null;
  email: string | null;
  avatar_url: string | null;
  identity_status: string;
  skills: string[];
  availability: WorkerAvailability;
  rating_avg: number;
  rating_count: number;
  completed_orders: number;
  city: string | null;
  current_lat: number | null;
  current_lng: number | null;
}

export interface Order {
  id: string;
  customer_id: string;
  customer_full_name: string | null;
  customer_avatar_url: string | null;
  worker_id: string | null;
  worker_full_name: string | null;
  worker_avatar_url: string | null;
  worker_rating_avg: number | null;
  worker_rating_count: number | null;
  description: string;
  budget_amount: number;
  city: string | null;
  address: string;
  scheduled_at: string;
  status: OrderStatus;
  assigned_at: string | null;
  decision_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Review {
  id: string;
  order_id: string;
  customer_id: string;
  worker_id: string;
  score: number;
  comment: string | null;
  created_at: string;
  order_title: string | null;
  customer_full_name: string | null;
}

export interface Notification {
  id: string;
  user_id: string;
  order_id: string | null;
  kind: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  order_id: string;
  sender_id: string;
  sender_role: UserRole | null;
  body: string;
  sent_at: string;
  read_at: string | null;
  client_message_id: string | null;
}

export type PaymentStatus = "pending" | "held" | "released" | "refunded" | "disputed";

export interface Payment {
  id: string;
  order_id: string;
  order_title: string | null;
  customer_id: string;
  worker_id: string | null;
  amount: number;
  service_fee: number;
  worker_amount: number;
  status: PaymentStatus;
  created_at: string;
  updated_at: string;
}

export interface Wallet {
  user_id: string;
  balance_available: number;
  balance_paid_out: number;
}

export interface Payout {
  id: string;
  worker_id: string;
  amount: number;
  status: "paid";
  created_at: string;
}

export interface PaymentsDashboard {
  wallet: Wallet;
  payments: Payment[];
  payouts: Payout[];
  hold_total: number;
}

export interface AdminDisputeDetail {
  order: Order;
  payment: Payment | null;
  messages: ChatMessage[];
}
