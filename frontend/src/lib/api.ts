import type { AdminDisputeDetail, ChatMessage, Notification, Order, PaymentsDashboard, Payout, Review, User, UserRole, Worker, WorkerAvailability } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_PREFIX = `${API_URL}/api/v1`;

interface CustomerPayload {
  full_name: string;
  phone?: string;
  email?: string;
}

interface WorkerPayload extends CustomerPayload {
  skills: string[];
  current_lat?: number | null;
  current_lng?: number | null;
}

interface OrderPayload {
  customer_id: string;
  description: string;
  budget_amount: number;
  address: string;
  scheduled_at: string;
}

interface AuthRegisterPayload {
  full_name: string;
  email: string;
  password: string;
  role: Exclude<UserRole, "admin">;
  phone?: string | null;
  skills?: string[];
}

interface AuthLoginPayload {
  email: string;
  password: string;
}

interface ProfileUpdatePayload {
  full_name: string;
  email: string;
  phone?: string | null;
}

interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

interface AvatarUpdatePayload {
  avatar_url?: string | null;
}

interface IdentityVerificationPayload {
  passport_full_name: string;
  passport_number: string;
}

interface MyOrderPayload {
  description: string;
  budget_amount: number;
  address: string;
  scheduled_at: string;
}

interface MessagePayload {
  body: string;
  client_message_id?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: User | Worker;
}

function authHeaders(token?: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const payload = await response.json();
      message = payload.detail ?? message;
    } catch {
      // Plain text or empty error response.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function register(payload: AuthRegisterPayload): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: AuthLoginPayload): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMe(token: string): Promise<User | Worker> {
  return request<User | Worker>("/auth/me", {
    headers: authHeaders(token),
  });
}

export function updateProfile(token: string, payload: ProfileUpdatePayload): Promise<User | Worker> {
  return request<User | Worker>("/auth/me/profile", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function changePassword(token: string, payload: PasswordChangePayload): Promise<User | Worker> {
  return request<User | Worker>("/auth/me/password", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function updateAvatar(token: string, payload: AvatarUpdatePayload): Promise<User | Worker> {
  return request<User | Worker>("/auth/me/avatar", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function verifyIdentity(token: string, payload: IdentityVerificationPayload): Promise<User | Worker> {
  return request<User | Worker>("/auth/me/identity", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function createCustomer(payload: CustomerPayload): Promise<User> {
  return request<User>("/customers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createWorker(payload: WorkerPayload): Promise<Worker> {
  return request<Worker>("/workers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listWorkers(availableOnly = false): Promise<Worker[]> {
  return request<Worker[]>(`/workers?available_only=${availableOnly}`);
}

export function setWorkerAvailability(workerId: string, availability: WorkerAvailability): Promise<Worker> {
  return request<Worker>(`/workers/${workerId}/availability?availability=${availability}`, {
    method: "POST",
  });
}

export function getMyWorkerProfile(token: string): Promise<Worker> {
  return request<Worker>("/workers/me", {
    headers: authHeaders(token),
  });
}

export function setMyWorkerAvailability(token: string, availability: WorkerAvailability): Promise<Worker> {
  return request<Worker>(`/workers/me/availability?availability=${availability}`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function createOrder(payload: OrderPayload): Promise<Order> {
  return request<Order>("/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createMyOrder(token: string, payload: MyOrderPayload): Promise<Order> {
  return request<Order>("/orders/me", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function listOrders(params: { customer_id?: string; worker_id?: string } = {}): Promise<Order[]> {
  const searchParams = new URLSearchParams();
  if (params.customer_id) {
    searchParams.set("customer_id", params.customer_id);
  }
  if (params.worker_id) {
    searchParams.set("worker_id", params.worker_id);
  }
  const query = searchParams.toString();
  return request<Order[]>(`/orders${query ? `?${query}` : ""}`);
}

export function listMyOrders(token: string): Promise<Order[]> {
  return request<Order[]>("/orders/me", {
    headers: authHeaders(token),
  });
}

export function listMessages(token: string, orderId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/orders/${orderId}/messages`, {
    headers: authHeaders(token),
  });
}

export function getUnreadMessagesCount(token: string): Promise<number> {
  return request<number>("/messages/unread-count", {
    headers: authHeaders(token),
  });
}

export function getMyPayments(token: string): Promise<PaymentsDashboard> {
  return request<PaymentsDashboard>("/payments/me", {
    headers: authHeaders(token),
  });
}

export function requestMyPayout(token: string): Promise<Payout> {
  return request<Payout>("/payments/me/payout", {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function sendMessage(token: string, orderId: string, payload: MessagePayload): Promise<ChatMessage> {
  return request<ChatMessage>(`/orders/${orderId}/messages`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function acceptOrder(orderId: string, workerId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/accept`, {
    method: "POST",
    body: JSON.stringify({ worker_id: workerId }),
  });
}

export function acceptMyOrder(token: string, orderId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/accept/me`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function declineOrder(orderId: string, workerId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/decline`, {
    method: "POST",
    body: JSON.stringify({ worker_id: workerId }),
  });
}

export function declineMyOrder(token: string, orderId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/decline/me`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function startOrder(orderId: string, workerId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/start`, {
    method: "POST",
    body: JSON.stringify({ worker_id: workerId }),
  });
}

export function startMyOrder(token: string, orderId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/start/me`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function completeOrder(orderId: string, workerId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/complete`, {
    method: "POST",
    body: JSON.stringify({ worker_id: workerId }),
  });
}

export function completeMyOrder(token: string, orderId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/complete/me`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function disputeMyOrder(token: string, orderId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/dispute/me`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function confirmMyOrderCompletion(token: string, orderId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/confirm-complete/me`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function reviewOrder(orderId: string, customerId: string, score: number, comment: string): Promise<Review> {
  return request<Review>(`/orders/${orderId}/review`, {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId, score, comment: comment || null }),
  });
}

export function reviewMyOrder(token: string, orderId: string, score: number, comment: string): Promise<Review> {
  return request<Review>(`/orders/${orderId}/review/me`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ score, comment: comment || null }),
  });
}

export function listMyWorkerReviews(token: string): Promise<Review[]> {
  return request<Review[]>("/workers/me/reviews", {
    headers: authHeaders(token),
  });
}

export function listNotifications(userId: string, unreadOnly = false): Promise<Notification[]> {
  return request<Notification[]>(`/notifications?user_id=${userId}&unread_only=${unreadOnly}`);
}

export function listMyNotifications(token: string, unreadOnly = false): Promise<Notification[]> {
  return request<Notification[]>(`/notifications/me?unread_only=${unreadOnly}`, {
    headers: authHeaders(token),
  });
}

export function listAdminDisputes(token: string): Promise<Order[]> {
  return request<Order[]>("/admin/disputes", {
    headers: authHeaders(token),
  });
}

export function getAdminDispute(token: string, orderId: string): Promise<AdminDisputeDetail> {
  return request<AdminDisputeDetail>(`/admin/disputes/${orderId}`, {
    headers: authHeaders(token),
  });
}

export function resolveAdminDispute(
  token: string,
  orderId: string,
  resolution: "release_to_worker" | "refund_customer",
  note?: string,
): Promise<AdminDisputeDetail> {
  return request<AdminDisputeDetail>(`/admin/disputes/${orderId}/resolve`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ resolution, note: note || null }),
  });
}
