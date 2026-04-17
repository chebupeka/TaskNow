<script lang="ts">
  import { onMount } from "svelte";
  import {
    acceptMyOrder,
    changePassword,
    confirmMyOrderCompletion,
    completeMyOrder,
    createMyOrder,
    disputeMyOrder,
    getAdminDispute,
    getMyPayments,
    getMe,
    getUnreadMessagesCount,
    listAdminDisputes,
    listMessages,
    listMyNotifications,
    listMyOrders,
    listMyWorkerReviews,
    login,
    register,
    requestMyPayout,
    resolveAdminDispute,
    reviewMyOrder,
    sendMessage,
    setMyWorkerAvailability,
    startMyOrder,
    updateAvatar,
    updateProfile,
    verifyIdentity,
  } from "./lib/api";
  import type { AdminDisputeDetail, ChatMessage, Notification, Order, OrderStatus, Payment, PaymentsDashboard, PaymentStatus, Review, User, UserRole, Worker } from "./lib/types";

  type Screen = "home" | "login" | "register" | "dashboard" | "create";
  type Role = Exclude<UserRole, "admin">;
  type DashboardSection = "tasks" | "payments" | "messages" | "reviews" | "settings";
  type ChatMessageView = ChatMessage & { pending?: boolean };

  const tokenStorageKey = "tasknow.accessToken";
  const screenStorageKey = "tasknow.activeScreen";
  const dashboardSectionStorageKey = "tasknow.dashboardSection";
  const paymentBadgeSeenCountStorageKey = "tasknow.paymentBadgeSeenCount";
  const heroImage =
    "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=1200&q=85";
  const authImage =
    "https://images.unsplash.com/photo-1621905252507-b35492cc74b4?auto=format&fit=crop&w=900&q=85";
  const workerImage =
    "https://images.unsplash.com/photo-1604762524889-3e2fcc145683?auto=format&fit=crop&w=900&q=85";

  const categories = ["Погрузка", "Уборка", "Доставка", "Сборка мебели", "Склад"];
  const skillOptions = ["Погрузка", "Уборка", "Доставка", "Сборка мебели", "Склад", "Другое"];
  const statusLabels: Record<OrderStatus, string> = {
    pending: "Ищем исполнителя",
    assigned: "Ждем ответа исполнителя",
    accepted: "Принят",
    in_progress: "В работе",
    completion_requested: "Ожидает подтверждения",
    completed: "Завершена",
    reviewed: "Завершена",
    disputed: "Спор открыт",
    canceled: "Отменен",
  };
  const paymentStatusLabels: Record<PaymentStatus, string> = {
    pending: "Ожидает резерва",
    held: "Зарезервировано",
    released: "Выплачено работнику",
    refunded: "Возврат",
    disputed: "Спор",
  };
  let activeScreen: Screen = "home";
  let selectedRole: Role = "customer";
  let activeTab: "active" | "done" = "active";
  let dashboardSection: DashboardSection = "tasks";
  let loading = false;
  let backgroundRefreshing = false;
  let navigationRestored = false;
  let notice = "";
  let noticeTimer: ReturnType<typeof setTimeout> | null = null;
  let error = "";
  let accessToken = "";
  let currentUser: User | Worker | null = null;
  let orders: Order[] = [];
  let notifications: Notification[] = [];
  let paymentsDashboard: PaymentsDashboard | null = null;
  let workerReviews: Review[] = [];
  let unreadMessagesCount = 0;
  let chatOrderId = "";
  let chatMessages: ChatMessageView[] = [];
  let chatDraft = "";
  let selectedOrder: Order | null = null;
  let workerProfileOpen = false;
  let adminDisputes: Order[] = [];
  let selectedAdminDispute: AdminDisputeDetail | null = null;
  let adminDisputeId = "";
  let adminNote = "";
  let rawPaymentBadgeCount = 0;
  let seenPaymentBadgeCount = 0;

  let loginEmail = "customer@tasknow.local";
  let loginPassword = "password123";
  let registerName = "Мария Иванова";
  let registerEmail = "customer@tasknow.local";
  let registerPhone = "+7 900 000-10-01";
  let registerPassword = "password123";
  let registerCity = "Москва";
  let selectedSkills: string[] = ["Погрузка"];

  let taskTitle = "Разгрузить мебель";
  let taskDescription = "Разгрузить мебель и аккуратно поднять коробки на второй этаж.";
  let taskBudget = "5000";
  let taskCategory = categories[0];
  let taskCity = "Москва";
  let taskLocation = "Москва, ул. Тверская, 12";
  let taskScheduledAt = localDateTimeInput(Date.now() + 2 * 60 * 60 * 1000);
  let reviewScore = 5;
  let reviewComment = "Работа выполнена аккуратно";
  let settingsName = "";
  let settingsEmail = "";
  let settingsPhone = "";
  let settingsCity = "";
  let settingsAvatarUrl = "";
  let avatarUploadHint = "PNG или JPG, квадрат 512x512 px, до 1 МБ.";
  let avatarEditorOpen = false;
  let avatarSourceUrl = "";
  let avatarScale = 1;
  let avatarOffsetX = 0;
  let avatarOffsetY = 0;
  let avatarImageSize = { width: 1, height: 1 };
  let avatarDragStart: { x: number; y: number; offsetX: number; offsetY: number } | null = null;
  let currentPassword = "";
  let newPassword = "";
  let passportFullName = "";
  let passportNumber = "";

  $: role = getCurrentRole(currentUser);
  $: isWorker = role === "worker";
  $: isCustomer = role === "customer";
  $: isAdmin = role === "admin";
  $: activeOrders = orders.filter((order) => !["completed", "reviewed", "disputed", "canceled"].includes(order.status));
  $: doneOrders = orders.filter((order) => ["completed", "reviewed", "disputed", "canceled"].includes(order.status));
  $: visibleOrders = activeTab === "active" ? activeOrders : doneOrders;
  $: chatOrders = orders.filter((order) => ["accepted", "in_progress", "completion_requested", "disputed"].includes(order.status));
  $: selectedChatOrder = chatOrders.find((order) => order.id === chatOrderId) ?? chatOrders[0] ?? null;
  $: unreadNotifications = notifications.filter((notification) => !notification.is_read);
  $: workerProfile = isWorker ? (currentUser as Worker) : null;
  $: workerOnShift = workerProfile?.availability !== "offline";
  $: workerHasActiveOrder = isWorker && activeOrders.some((order) =>
    ["accepted", "in_progress", "completion_requested"].includes(order.status)
  );
  $: taskBadgeCount = activeOrders.filter((order) =>
    isCustomer ? order.status === "completion_requested" : order.status === "assigned"
  ).length;
  $: rawPaymentBadgeCount = paymentsDashboard?.payments.filter((payment) =>
    isCustomer ? payment.status === "held" : payment.status === "released"
  ).length ?? 0;
  $: paymentBadgeCount = dashboardSection === "payments" ? 0 : Math.max(0, rawPaymentBadgeCount - seenPaymentBadgeCount);
  $: selectedOrderPayment = getOrderPayment(selectedOrder);
  $: if (navigationRestored) {
    localStorage.setItem(screenStorageKey, activeScreen);
    localStorage.setItem(dashboardSectionStorageKey, dashboardSection);
  }
  $: if (navigationRestored && dashboardSection === "payments" && rawPaymentBadgeCount !== seenPaymentBadgeCount) {
    seenPaymentBadgeCount = rawPaymentBadgeCount;
    localStorage.setItem(paymentBadgeSeenCountStorageKey, String(seenPaymentBadgeCount));
  }

  function setScreen(screen: Screen) {
    activeScreen = screen;
    clearFeedback();
    if (screen === "dashboard" && accessToken) {
      void run(refreshSession);
    }
  }

  function clearFeedback() {
    error = "";
    notice = "";
    if (noticeTimer) {
      clearTimeout(noticeTimer);
      noticeTimer = null;
    }
  }

  function flashNotice(message: string) {
    notice = message;
    if (noticeTimer) clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => {
      if (notice === message) notice = "";
      noticeTimer = null;
    }, 3200);
  }

  function setTaskTab(tab: "active" | "done") {
    activeTab = tab;
    clearFeedback();
  }

  function setDashboardSection(section: DashboardSection) {
    dashboardSection = section;
    clearFeedback();
    if (section === "payments") {
      seenPaymentBadgeCount = rawPaymentBadgeCount;
      localStorage.setItem(paymentBadgeSeenCountStorageKey, String(seenPaymentBadgeCount));
    }
    if (section === "messages") {
      void run(loadActiveChat);
    }
  }

  function localDateTimeInput(value: number) {
    const date = new Date(value);
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return localDate.toISOString().slice(0, 16);
  }

  function getCurrentRole(user: User | Worker | null): UserRole | null {
    if (!user) return null;
    return user.role;
  }

  function formatPrice(value: string) {
    const amount = Number(value.replace(/\D/g, "")) || 0;
    return new Intl.NumberFormat("ru-RU").format(amount) + " ₽";
  }

  function formatMoney(value: number) {
    return new Intl.NumberFormat("ru-RU").format(value) + " ₽";
  }

  function formatDate(value: string) {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }

  function makeDescription() {
    return `${taskTitle}. ${taskDescription} Категория: ${taskCategory}.`;
  }

  function normalizePhone(value: string) {
    const normalized = value.trim().replace(/[\s().-]/g, "");
    if (!/^(?:\+7|8)\d{10}$/.test(normalized)) {
      throw new Error("Телефон должен быть в формате +7XXXXXXXXXX или 8XXXXXXXXXX");
    }
    return `+7${normalized.slice(-10)}`;
  }

  function getOrderTitle(order: Order) {
    return order.description.split(".")[0] || "Задача";
  }

  function getStatusLabel(order: Order) {
    if (isWorker && order.status === "assigned") return "Новый заказ";
    return statusLabels[order.status];
  }

  function getWorkerRating(order: Order) {
    return order.worker_rating_count ? order.worker_rating_avg?.toFixed(1) : "0";
  }

  function hasConfirmedWorker(order: Order) {
    return Boolean(
      order.worker_id && ["accepted", "in_progress", "completion_requested", "completed", "reviewed"].includes(order.status),
    );
  }

  function getChatPeerName(order: Order | null) {
    if (!order) return "Чат";
    return isCustomer ? order.worker_full_name ?? "Исполнитель" : order.customer_full_name ?? "Заказчик";
  }

  function getChatPeerAvatar(order: Order | null) {
    if (!order) return null;
    return isCustomer ? order.worker_avatar_url : order.customer_avatar_url;
  }

  function isOwnMessage(message: ChatMessageView) {
    return Boolean(currentUser && message.sender_id === currentUser.id);
  }

  function isAdminMessage(message: ChatMessageView) {
    return message.sender_role === "admin";
  }

  function getMessageStatus(message: ChatMessageView) {
    if (message.pending) return "clock";
    return message.read_at ? "read" : "sent";
  }

  function getPaymentTotal(status: PaymentStatus) {
    return paymentsDashboard?.payments
      .filter((payment) => payment.status === status)
      .reduce((total, payment) => total + payment.amount, 0) ?? 0;
  }

  function getPaymentFeeText(payment: Payment) {
    return payment.status === "refunded" ? "без комиссии" : `комиссия ${formatMoney(payment.service_fee)}`;
  }

  function shouldShowPaymentCommission(payment: Payment | null) {
    return Boolean(payment && payment.status !== "refunded");
  }

  function getOrderPayment(order: Order | null): Payment | null {
    if (!order) return null;
    return paymentsDashboard?.payments.find((payment) => payment.order_id === order.id) ?? null;
  }

  function restoreScreen(value: string | null): Screen {
    return ["home", "login", "register", "dashboard", "create"].includes(value ?? "")
      ? (value as Screen)
      : "home";
  }

  function restoreDashboardSection(value: string | null): DashboardSection {
    return ["tasks", "payments", "messages", "reviews", "settings"].includes(value ?? "")
      ? (value as DashboardSection)
      : "tasks";
  }

  function getTimeline(order: Order) {
    const items = [
      { label: "Задача создана", date: order.created_at, active: true },
      { label: "Исполнитель назначен", date: order.assigned_at, active: Boolean(order.assigned_at) },
      { label: "Заказ принят", date: order.decision_at, active: ["accepted", "in_progress", "completion_requested", "completed", "reviewed", "disputed"].includes(order.status) },
      { label: "Работа начата", date: order.started_at, active: Boolean(order.started_at) },
      { label: "Запрос на завершение", date: order.updated_at, active: ["completion_requested", "completed", "reviewed"].includes(order.status) },
      { label: order.status === "disputed" ? "Открыт спор" : "Задача завершена", date: order.completed_at ?? order.updated_at, active: ["completed", "reviewed", "disputed"].includes(order.status) },
    ];
    return items.filter((item) => item.active);
  }

  function openOrderDetails(order: Order) {
    selectedOrder = order;
    workerProfileOpen = false;
  }

  async function openDispute(order: Order) {
    if (!accessToken) throw new Error("Сначала войдите в аккаунт");
    await disputeMyOrder(accessToken, order.id);
    await refreshSession();
    if (dashboardSection === "messages") {
      await loadChat(order.id);
    }
    selectedOrder = orders.find((item) => item.id === order.id) ?? null;
    flashNotice("Спор открыт, платеж заморожен");
  }

  async function run(action: () => Promise<void>) {
    loading = true;
    error = "";
    if (noticeTimer) {
      clearTimeout(noticeTimer);
      noticeTimer = null;
    }
    try {
      await action();
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Неизвестная ошибка";
    } finally {
      loading = false;
    }
  }

  async function refreshSession() {
    if (!accessToken) return;
    currentUser = await getMe(accessToken);
    syncSettingsForm();
    if (getCurrentRole(currentUser) === "admin") {
      adminDisputes = await listAdminDisputes(accessToken);
      if (adminDisputes.length > 0) {
        const nextId = adminDisputes.some((order) => order.id === adminDisputeId) ? adminDisputeId : adminDisputes[0].id;
        await loadAdminDispute(nextId);
      } else {
        selectedAdminDispute = null;
        adminDisputeId = "";
      }
      orders = [];
      notifications = [];
      paymentsDashboard = null;
      workerReviews = [];
      unreadMessagesCount = 0;
      return;
    }
    orders = await listMyOrders(accessToken);
    notifications = getCurrentRole(currentUser) === "worker" ? await listMyNotifications(accessToken, true) : [];
    paymentsDashboard = await getMyPayments(accessToken);
    workerReviews = getCurrentRole(currentUser) === "worker" ? await listMyWorkerReviews(accessToken) : [];
    unreadMessagesCount = await getUnreadMessagesCount(accessToken);
    if (dashboardSection === "messages") {
      await loadActiveChat();
    }
  }

  async function refreshDashboardData() {
    if (!accessToken || activeScreen !== "dashboard" || loading || backgroundRefreshing) return;
    backgroundRefreshing = true;
    try {
      const freshUser = await getMe(accessToken);
      currentUser = freshUser;
      const freshRole = getCurrentRole(freshUser);

      if (freshRole === "admin") {
        adminDisputes = await listAdminDisputes(accessToken);
        if (selectedAdminDispute) {
          await loadAdminDispute(selectedAdminDispute.order.id);
        }
        return;
      }

      orders = await listMyOrders(accessToken);
      notifications = freshRole === "worker" ? await listMyNotifications(accessToken, true) : [];
      paymentsDashboard = await getMyPayments(accessToken);
      workerReviews = freshRole === "worker" ? await listMyWorkerReviews(accessToken) : [];
      unreadMessagesCount = await getUnreadMessagesCount(accessToken);

      if (selectedOrder) {
        selectedOrder = orders.find((order) => order.id === selectedOrder?.id) ?? selectedOrder;
      }
      if (dashboardSection === "messages") {
        await loadActiveChat();
      }
    } finally {
      backgroundRefreshing = false;
    }
  }

  function syncSettingsForm() {
    if (!currentUser) return;
    settingsName = currentUser.full_name;
    settingsEmail = currentUser.email ?? "";
    settingsPhone = currentUser.phone ?? "";
    settingsCity = getCurrentRole(currentUser) === "worker" ? (currentUser as Worker).city ?? "" : "";
    settingsAvatarUrl = currentUser.avatar_url ?? "";
    passportFullName = currentUser.full_name;
  }

  async function submitLogin() {
    const response = await login({ email: loginEmail, password: loginPassword });
    accessToken = response.access_token;
    currentUser = response.user;
    localStorage.setItem(tokenStorageKey, accessToken);
    await refreshSession();
    activeScreen = "dashboard";
    flashNotice("Вы вошли в аккаунт");
  }

  async function loadAdminDispute(orderId: string) {
    if (!accessToken) return;
    adminDisputeId = orderId;
    selectedAdminDispute = await getAdminDispute(accessToken, orderId);
  }

  async function submitAdminMessage() {
    const body = chatDraft.trim();
    if (!accessToken || !selectedAdminDispute || !body) return;
    await sendMessage(accessToken, selectedAdminDispute.order.id, { body });
    chatDraft = "";
    await loadAdminDispute(selectedAdminDispute.order.id);
  }

  async function resolveSelectedDispute(resolution: "release_to_worker" | "refund_customer") {
    if (!accessToken || !selectedAdminDispute) return;
    await resolveAdminDispute(accessToken, selectedAdminDispute.order.id, resolution, adminNote.trim() || undefined);
    adminNote = "";
    adminDisputes = await listAdminDisputes(accessToken);
    if (adminDisputes.length > 0) {
      await loadAdminDispute(adminDisputes[0].id);
    } else {
      selectedAdminDispute = null;
      adminDisputeId = "";
    }
    flashNotice(resolution === "release_to_worker" ? "Спор закрыт: выплата исполнителю" : "Спор закрыт: возврат заказчику");
  }

  async function submitRegister() {
    const response = await register({
      full_name: registerName,
      email: registerEmail,
      phone: registerPhone ? normalizePhone(registerPhone) : null,
      password: registerPassword,
      role: selectedRole,
      city: selectedRole === "worker" ? registerCity : null,
      skills:
        selectedRole === "worker"
          ? selectedSkills
          : [],
    });
    accessToken = response.access_token;
    currentUser = response.user;
    localStorage.setItem(tokenStorageKey, accessToken);
    await refreshSession();
    activeScreen = "dashboard";
    flashNotice("Аккаунт создан");
  }

  async function submitTask() {
    if (!accessToken) {
      activeScreen = "login";
      throw new Error("Сначала войдите в аккаунт заказчика");
    }
    if (role !== "customer") {
      throw new Error("Создавать задачи может только заказчик");
    }
    await createMyOrder(accessToken, {
      description: makeDescription(),
      budget_amount: Number(taskBudget.replace(/\D/g, "")) || 0,
      city: taskCity,
      address: taskLocation,
      scheduled_at: new Date(taskScheduledAt).toISOString(),
    });
    await refreshSession();
    activeScreen = "dashboard";
    flashNotice("Задача опубликована");
  }

  async function setAvailable() {
    if (!accessToken || role !== "worker") {
      throw new Error("Доступность может менять только работник");
    }
    const workerCity = workerProfile?.city;
    if (!workerCity) {
      throw new Error("Укажите город в профиле работника, чтобы получать заказы рядом");
    }
    currentUser = await setMyWorkerAvailability(accessToken, "available", workerCity);
    await refreshSession();
    flashNotice("Вы на смене");
  }

  async function setOffline() {
    if (!accessToken || role !== "worker") {
      throw new Error("Доступность может менять только работник");
    }
    currentUser = await setMyWorkerAvailability(accessToken, "offline");
    await refreshSession();
    flashNotice("Смена завершена");
  }

  async function handleWorkerAction(order: Order, action: "accept" | "start" | "complete") {
    if (!accessToken || role !== "worker") {
      throw new Error("Это действие доступно только работнику");
    }

    if (action === "accept") await acceptMyOrder(accessToken, order.id);
    if (action === "start") await startMyOrder(accessToken, order.id);
    if (action === "complete") await completeMyOrder(accessToken, order.id);
    await refreshSession();
  }

  async function confirmCompletion(order: Order) {
    if (!accessToken || role !== "customer") {
      throw new Error("Подтвердить завершение может только заказчик");
    }
    await confirmMyOrderCompletion(accessToken, order.id);
    if (chatOrderId === order.id) {
      chatOrderId = "";
      chatMessages = [];
    }
    await refreshSession();
    flashNotice("Задача завершена");
  }

  async function loadActiveChat() {
    if (!accessToken) return;
    const nextOrder = chatOrders.find((order) => order.id === chatOrderId) ?? chatOrders[0];
    if (!nextOrder) {
      chatOrderId = "";
      chatMessages = [];
      return;
    }
    await loadChat(nextOrder.id);
  }

  async function loadChat(orderId: string) {
    if (!accessToken) return;
    chatOrderId = orderId;
    chatMessages = await listMessages(accessToken, orderId);
    unreadMessagesCount = await getUnreadMessagesCount(accessToken);
  }

  async function submitChatMessage() {
    const body = chatDraft.trim();
    if (!accessToken || !selectedChatOrder || !currentUser || !body) return;

    const clientMessageId = `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const pendingMessage: ChatMessageView = {
      id: `pending-${clientMessageId}`,
      order_id: selectedChatOrder.id,
      sender_id: currentUser.id,
      sender_role: currentUser.role,
      body,
      sent_at: new Date().toISOString(),
      read_at: null,
      client_message_id: clientMessageId,
      pending: true,
    };

    chatDraft = "";
    chatMessages = [...chatMessages, pendingMessage];
    try {
      const savedMessage = await sendMessage(accessToken, selectedChatOrder.id, {
        body,
        client_message_id: clientMessageId,
      });
      chatMessages = chatMessages.map((message) =>
        message.client_message_id === clientMessageId ? savedMessage : message
      );
      unreadMessagesCount = await getUnreadMessagesCount(accessToken);
    } catch (caught) {
      chatMessages = chatMessages.filter((message) => message.client_message_id !== clientMessageId);
      chatDraft = body;
      throw caught;
    }
  }

  function toggleSkill(skill: string) {
    selectedSkills = selectedSkills.includes(skill)
      ? selectedSkills.filter((selectedSkill) => selectedSkill !== skill)
      : [...selectedSkills, skill];
  }

  async function submitReview(order: Order) {
    if (!accessToken || role !== "customer") {
      throw new Error("Оценку может поставить только заказчик");
    }
    await reviewMyOrder(accessToken, order.id, reviewScore, reviewComment);
    await refreshSession();
    flashNotice("Оценка сохранена");
  }

  async function submitPayoutRequest() {
    if (!accessToken || role !== "worker") {
      throw new Error("Вывод доступен только работнику");
    }
    await requestMyPayout(accessToken);
    paymentsDashboard = await getMyPayments(accessToken);
    flashNotice("Выплата оформлена");
  }

  async function submitProfileSettings() {
    if (!accessToken) throw new Error("Сначала войдите в аккаунт");
    currentUser = await updateProfile(accessToken, {
      full_name: settingsName,
      email: settingsEmail,
      phone: settingsPhone ? normalizePhone(settingsPhone) : null,
      city: isWorker ? settingsCity : null,
    });
    syncSettingsForm();
    flashNotice("Профиль обновлен");
  }

  async function submitAvatarSettings() {
    if (!accessToken) throw new Error("Сначала войдите в аккаунт");
    currentUser = await updateAvatar(accessToken, {
      avatar_url: settingsAvatarUrl.trim() || null,
    });
    syncSettingsForm();
    flashNotice("Аватар обновлен");
  }

  async function handleAvatarFile(file: File | undefined) {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      throw new Error("Аватар должен быть PNG, JPG или WEBP");
    }
    if (file.size > 1024 * 1024) {
      throw new Error("Файл аватарки должен быть не больше 1 МБ");
    }

    avatarSourceUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("Не удалось прочитать файл"));
      reader.readAsDataURL(file);
    });
    avatarScale = 1;
    avatarOffsetX = 0;
    avatarOffsetY = 0;
    const image = await loadImage(avatarSourceUrl);
    avatarImageSize = { width: image.width, height: image.height };
    avatarEditorOpen = true;
    avatarUploadHint = "Настройте кадрирование и нажмите «Применить».";
  }

  async function handleAvatarInput(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    await handleAvatarFile(input.files?.[0]);
    input.value = "";
  }

  async function handleAvatarDrop(event: DragEvent) {
    event.preventDefault();
    await handleAvatarFile(event.dataTransfer?.files[0]);
  }

  function startAvatarDrag(event: PointerEvent) {
    event.preventDefault();
    avatarDragStart = {
      x: event.clientX,
      y: event.clientY,
      offsetX: avatarOffsetX,
      offsetY: avatarOffsetY,
    };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  function moveAvatarDrag(event: PointerEvent) {
    if (!avatarDragStart) return;
    setAvatarOffset(
      avatarDragStart.offsetX + event.clientX - avatarDragStart.x,
      avatarDragStart.offsetY + event.clientY - avatarDragStart.y,
    );
  }

  function endAvatarDrag() {
    avatarDragStart = null;
  }

  async function loadImage(src: string) {
    return await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Не удалось открыть изображение"));
      image.src = src;
    });
  }

  function getAvatarBounds(scale = avatarScale) {
    const frame = 280;
    const baseScale = Math.min(frame / avatarImageSize.width, frame / avatarImageSize.height);
    const width = avatarImageSize.width * baseScale * scale;
    const height = avatarImageSize.height * baseScale * scale;

    return {
      x: Math.max(0, (width - frame) / 2),
      y: Math.max(0, (height - frame) / 2),
    };
  }

  function setAvatarOffset(x: number, y: number, scale = avatarScale) {
    const bounds = getAvatarBounds(scale);
    avatarOffsetX = Math.min(bounds.x, Math.max(-bounds.x, x));
    avatarOffsetY = Math.min(bounds.y, Math.max(-bounds.y, y));
  }

  function setAvatarScale(value: number) {
    avatarScale = value;
    setAvatarOffset(avatarOffsetX, avatarOffsetY, value);
  }

  async function applyAvatarCrop() {
    const image = await loadImage(avatarSourceUrl);
    const canvas = document.createElement("canvas");
    const size = 512;
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Не удалось подготовить аватар");

    context.fillStyle = "#f5f2dc";
    context.fillRect(0, 0, size, size);
    const baseScale = Math.min(size / image.width, size / image.height);
    const drawWidth = image.width * baseScale * avatarScale;
    const drawHeight = image.height * baseScale * avatarScale;
    const drawX = (size - drawWidth) / 2 + avatarOffsetX * (size / 280);
    const drawY = (size - drawHeight) / 2 + avatarOffsetY * (size / 280);
    context.drawImage(image, drawX, drawY, drawWidth, drawHeight);

    settingsAvatarUrl = canvas.toDataURL("image/jpeg", 0.88);
    avatarEditorOpen = false;
    avatarUploadHint = "Кадр готов. Нажмите «Обновить аватар».";
  }

  async function submitPasswordSettings() {
    if (!accessToken) throw new Error("Сначала войдите в аккаунт");
    currentUser = await changePassword(accessToken, {
      current_password: currentPassword,
      new_password: newPassword,
    });
    currentPassword = "";
    newPassword = "";
    flashNotice("Пароль изменен");
  }

  async function submitIdentitySettings() {
    if (!accessToken) throw new Error("Сначала войдите в аккаунт");
    currentUser = await verifyIdentity(accessToken, {
      passport_full_name: passportFullName,
      passport_number: passportNumber,
    });
    passportNumber = "";
    flashNotice("Личность подтверждена");
  }

  function logout() {
    localStorage.removeItem(tokenStorageKey);
    localStorage.setItem(screenStorageKey, "home");
    localStorage.setItem(dashboardSectionStorageKey, "tasks");
    localStorage.removeItem(paymentBadgeSeenCountStorageKey);
    accessToken = "";
    currentUser = null;
    orders = [];
    notifications = [];
    adminDisputes = [];
    selectedAdminDispute = null;
    adminDisputeId = "";
    activeScreen = "home";
    dashboardSection = "tasks";
    seenPaymentBadgeCount = 0;
  }

  onMount(() => {
    accessToken = localStorage.getItem(tokenStorageKey) ?? "";
    dashboardSection = restoreDashboardSection(localStorage.getItem(dashboardSectionStorageKey));
    seenPaymentBadgeCount = Number(localStorage.getItem(paymentBadgeSeenCountStorageKey)) || 0;
    const savedScreen = restoreScreen(localStorage.getItem(screenStorageKey));
    activeScreen = accessToken ? savedScreen : savedScreen === "dashboard" ? "home" : savedScreen;
    navigationRestored = true;
    if (accessToken) {
      void run(refreshSession);
    }
    const dashboardPollTimer = setInterval(() => {
      void refreshDashboardData().catch(() => {
        // Polling must not interrupt the current UI flow.
      });
    }, 1200);

    return () => clearInterval(dashboardPollTimer);
  });
</script>

<main class="site-shell">
  <section class="screen-frame">
    <header class="topbar">
      <button class="brand" type="button" on:click={() => setScreen("home")} aria-label="TaskNow home">
        <span class="brand-mark">T</span>
        <span>TaskNow</span>
      </button>
      <nav aria-label="Основная навигация">
        <button class:active={activeScreen === "home"} type="button" on:click={() => setScreen("home")}>Главная</button>
        <button class:active={activeScreen === "dashboard"} type="button" on:click={() => setScreen("dashboard")}>
          Кабинет
        </button>
        {#if !isWorker && !isAdmin}
          <button class:active={activeScreen === "create"} type="button" on:click={() => setScreen("create")}>
            Создать задачу
          </button>
        {/if}
      </nav>
      <div class="top-actions">
        {#if currentUser}
          <button class="ghost-button" type="button" on:click={logout}>Выйти</button>
        {:else}
          <button class="ghost-button" type="button" on:click={() => setScreen("login")}>Войти</button>
          <button class="primary-button compact" type="button" on:click={() => setScreen("register")}>
            Начать
          </button>
        {/if}
      </div>
    </header>

    {#if notice}
      <div class="toast success">{notice}</div>
    {/if}
    {#if error}
      <div class="toast danger">{error}</div>
    {/if}

    {#if activeScreen === "home" && currentUser}
      <section class="signed-home page-section">
        <div class="signed-home-card">
          <p class="eyebrow">{isAdmin ? "Администрирование" : isWorker ? "Рабочая смена" : "Ваши задачи"}</p>
          <h1>{isAdmin ? "Разбирайте открытые споры" : isWorker ? "Проверьте новые назначения" : "Управляйте текущими заказами"}</h1>
          <p class="lead">
            {isAdmin
              ? "В админ-панели доступны спорные заказы, чат с участниками и решение по замороженному платежу."
              : isWorker
              ? "В кабинете видны назначенные задачи, запросы на подтверждение и уведомления по заказам."
              : "В кабинете можно отслеживать активные задачи, подтверждать завершение и оставлять оценку исполнителю."}
          </p>
          <div class="hero-actions">
            <button class="primary-button" type="button" on:click={() => setScreen("dashboard")}>Перейти в кабинет</button>
            {#if isCustomer}
              <button class="outline-button" type="button" on:click={() => setScreen("create")}>Создать задачу</button>
            {/if}
          </div>
        </div>
      </section>
    {:else if activeScreen === "home"}
      <section class="landing-page page-section">
        <div class="hero-grid">
          <div class="hero-copy">
            <p class="eyebrow">Маркетплейс ручного труда</p>
            <h1>Найди исполнителя за 2 минуты</h1>
            <p class="lead">
              Срочные задачи для дома, офиса и склада. TaskNow подберет свободного работника, покажет статус заказа и
              сохранит историю работы.
            </p>
            <div class="hero-actions">
              <button class="primary-button" type="button" on:click={() => setScreen("create")}>Создать задачу</button>
              <button class="outline-button" type="button" on:click={() => setScreen("register")}>Стать исполнителем</button>
            </div>
            <div class="trust-row" aria-label="Показатели сервиса">
              <div><strong>12 мин</strong><span>средний старт</span></div>
              <div><strong>4.9</strong><span>рейтинг работ</span></div>
              <div><strong>24/7</strong><span>поиск смен</span></div>
            </div>
          </div>

          <div class="hero-visual" aria-label="Превью мобильной карты и исполнителя">
            <img src={heroImage} alt="Работник на складе" />
            <div class="map-phone">
              <div class="phone-topline"></div>
              <div class="map-path"></div>
              <div class="map-pin pin-one"></div>
              <div class="map-pin pin-two"></div>
              <article class="driver-card">
                {@render Avatar(null)}
                <div>
                  <strong>Иван рядом</strong>
                  <span>4.9 ★ · 7 минут</span>
                </div>
              </article>
            </div>
          </div>
        </div>

        <section class="steps-section" aria-label="Как работает TaskNow">
          <div class="section-title">
            <p class="eyebrow">Как это работает</p>
            <h2>Три шага до закрытой задачи</h2>
          </div>
          <div class="steps-grid">
            <article class="step-card">
              {@render Icon("edit")}
              <span>01</span>
              <h3>Создай задачу</h3>
              <p>Опиши работу, адрес, бюджет и удобное время.</p>
            </article>
            <article class="step-card">
              {@render Icon("route")}
              <span>02</span>
              <h3>Система подберет исполнителя</h3>
              <p>Алгоритм учитывает доступность, рейтинг и активные заказы.</p>
            </article>
            <article class="step-card">
              {@render Icon("star")}
              <span>03</span>
              <h3>Оцени работу</h3>
              <p>После завершения оставь оценку и отзыв в истории.</p>
            </article>
          </div>
        </section>
      </section>
    {:else if activeScreen === "login"}
      <section class="auth-page page-section">
        <div class="auth-card">
          <div class="auth-copy">
            <p class="eyebrow">Добро пожаловать</p>
            <h1>Войти в TaskNow</h1>
            <p>Продолжите работу с заказами, сообщениями и выплатами.</p>
            <img src={authImage} alt="Электрик за работой" />
          </div>
          <form class="auth-form" on:submit|preventDefault={() => run(submitLogin)}>
            <label>
              Email или логин
              <input bind:value={loginEmail} type="text" placeholder="you@company.ru или admin" required />
            </label>
            <label>
              Password
              <input bind:value={loginPassword} type="password" placeholder="••••••••" required />
            </label>
            <button class="primary-button full" type="submit" disabled={loading}>Войти</button>
            <div class="form-links">
              <button type="button">Забыли пароль?</button>
              <button type="button" on:click={() => setScreen("register")}>Создать аккаунт</button>
            </div>
          </form>
        </div>
      </section>
    {:else if activeScreen === "register"}
      <section class="auth-page page-section">
        <div class="auth-card register-card">
          <div class="auth-copy">
            <p class="eyebrow">Новый аккаунт</p>
            <h1>Создать профиль</h1>
            <p>Выберите роль и начните принимать или размещать задачи.</p>
            <img src={workerImage} alt="Исполнитель на объекте" />
          </div>
          <form class="auth-form" on:submit|preventDefault={() => run(submitRegister)}>
            <label>
              Name
              <input bind:value={registerName} placeholder="Мария Иванова" required />
            </label>
            <label>
              Email
              <input bind:value={registerEmail} type="email" placeholder="mail@example.ru" required />
            </label>
            <label>
              Phone
              <input
                bind:value={registerPhone}
                inputmode="tel"
                pattern="(?:\+7|8)[0-9\s().-]{10,16}"
                placeholder="+7 900 000-10-01"
              />
            </label>
            <label>
              Password
              <input bind:value={registerPassword} type="password" placeholder="Минимум 8 символов" required />
            </label>
            {#if selectedRole === "worker"}
              <label>
                Город
                <input bind:value={registerCity} placeholder="Москва" required />
              </label>
              <fieldset class="skills-selector">
                <legend>Skills</legend>
                {#each skillOptions as skill}
                  <label class="skill-chip">
                    <input
                      checked={selectedSkills.includes(skill)}
                      type="checkbox"
                      on:change={() => toggleSkill(skill)}
                    />
                    <span>{skill}</span>
                  </label>
                {/each}
              </fieldset>
            {/if}
            <div class="role-selector" aria-label="Выбор роли">
              <button class:selected={selectedRole === "customer"} type="button" on:click={() => (selectedRole = "customer")}>
                Customer
              </button>
              <button class:selected={selectedRole === "worker"} type="button" on:click={() => (selectedRole = "worker")}>
                Worker
              </button>
            </div>
            <button class="primary-button full" type="submit" disabled={loading}>Создать аккаунт</button>
          </form>
        </div>
      </section>
    {:else if activeScreen === "dashboard"}
      <section class="dashboard-page page-section">
        <aside class="sidebar">
          <div class="profile-block">
            {@render Avatar(currentUser?.avatar_url ?? null)}
            <div>
              <strong>{currentUser?.full_name ?? "Гость"}</strong>
              <span>{role === "admin" ? "Администратор" : role === "worker" ? "Работник" : "Заказчик"} · TaskNow</span>
              {#if isWorker}
                <small class:online={workerOnShift} class="shift-dot">{workerOnShift ? "На смене" : "Не на смене"}</small>
              {/if}
            </div>
          </div>
          <nav class="side-menu" aria-label="Меню кабинета">
            {#if isAdmin}
              <button class:active={dashboardSection === "tasks"} type="button" on:click={() => setDashboardSection("tasks")}>
                {@render Icon("list")}Споры
                {#if adminDisputes.length > 0}
                  <span class="menu-badge">{adminDisputes.length}</span>
                {/if}
              </button>
            {:else}
              <button class:active={dashboardSection === "tasks"} type="button" on:click={() => setDashboardSection("tasks")}>
                {@render Icon("list")}Задачи
                {#if taskBadgeCount > 0}
                  <span class="menu-badge">{taskBadgeCount}</span>
                {/if}
              </button>
              <button class:active={dashboardSection === "payments"} type="button" on:click={() => setDashboardSection("payments")}>
                {@render Icon("wallet")}Платежи
                {#if paymentBadgeCount > 0}
                  <span class="menu-badge">{paymentBadgeCount}</span>
                {/if}
              </button>
              <button class:active={dashboardSection === "messages"} type="button" on:click={() => setDashboardSection("messages")}>
                {@render Icon("message")}Сообщения
                {#if unreadMessagesCount > 0}
                  <span class="menu-badge">{unreadMessagesCount > 99 ? "99+" : unreadMessagesCount}</span>
                {/if}
              </button>
              <button class:active={dashboardSection === "settings"} type="button" on:click={() => setDashboardSection("settings")}>
                {@render Icon("settings")}Настройки
              </button>
            {/if}
            {#if isWorker}
              <button class:active={dashboardSection === "reviews"} type="button" on:click={() => setDashboardSection("reviews")}>
                {@render Icon("star")}Отзывы
              </button>
            {/if}
          </nav>
          <div class="sidebar-action">
            {#if role === "worker"}
              {#if workerOnShift}
                <button
                  class="primary-button compact"
                  type="button"
                  disabled={loading || workerHasActiveOrder}
                  title={workerHasActiveOrder ? "Сначала завершите активную задачу" : undefined}
                  on:click={() => run(setOffline)}
                >
                  Завершить смену
                </button>
              {:else}
                <button
                  class="primary-button compact"
                  type="button"
                  disabled={loading}
                  title="Заказы назначаются по городу из профиля"
                  on:click={() => run(setAvailable)}
                >
                  Выйти на смену
                </button>
              {/if}
            {:else if isCustomer}
              <button class="primary-button compact" type="button" on:click={() => setScreen("create")}>Новая задача</button>
            {/if}
          </div>
        </aside>

        <section class="dashboard-main">
          <div class="dashboard-heading">
            <div>
              <p class="eyebrow">{isAdmin ? "Админ-панель" : isWorker ? "Кабинет исполнителя" : "Кабинет заказчика"}</p>
              <h1>{isAdmin ? "Разбор споров" : isWorker ? "Назначенные заказы" : "Мои задачи"}</h1>
            </div>
          </div>
          {#if isAdmin}
            <section class="chat-panel">
              {#if adminDisputes.length === 0}
                <article class="chat-empty">
                  <p class="eyebrow">Споры</p>
                  <h2>Открытых споров нет</h2>
                  <p>Когда заказчик или исполнитель откроет спор, он появится здесь вместе с платежом и перепиской.</p>
                </article>
              {:else}
                <div class="chat-order-tabs" aria-label="Выбор спора">
                  {#each adminDisputes as dispute}
                    <button class:active={selectedAdminDispute?.order.id === dispute.id} type="button" on:click={() => run(() => loadAdminDispute(dispute.id))}>
                      {getOrderTitle(dispute)}
                    </button>
                  {/each}
                </div>
                {#if selectedAdminDispute}
                  <article class="details-card">
                    <h3>{getOrderTitle(selectedAdminDispute.order)}</h3>
                    <p>{selectedAdminDispute.order.description}</p>
                    <span>{selectedAdminDispute.order.address} · {formatDate(selectedAdminDispute.order.scheduled_at)}</span>
                    <span>Заказчик: {selectedAdminDispute.order.customer_full_name ?? "Неизвестно"}</span>
                    <span>Исполнитель: {selectedAdminDispute.order.worker_full_name ?? "Неизвестно"}</span>
                  </article>
                  <article class="details-card">
                    <h3>Платеж</h3>
                    {#if selectedAdminDispute.payment}
                      <p>{paymentStatusLabels[selectedAdminDispute.payment.status]}</p>
                      <span>Бюджет: {formatMoney(selectedAdminDispute.payment.amount)}</span>
                      {#if shouldShowPaymentCommission(selectedAdminDispute.payment)}
                        <span>Комиссия сервиса: {formatMoney(selectedAdminDispute.payment.service_fee)}</span>
                        <span>К выплате исполнителю: {formatMoney(selectedAdminDispute.payment.worker_amount)}</span>
                      {:else}
                        <span>Возврат заказчику без комиссии</span>
                      {/if}
                    {:else}
                      <p>Платеж не найден</p>
                    {/if}
                  </article>
                  <article class="chat-shell">
                    <header class="chat-header">
                      {@render Avatar(null)}
                      <div>
                        <strong>Чат спора</strong>
                        <span>Администратор подключен третьим участником</span>
                      </div>
                    </header>
                    <div class="message-list" aria-live="polite">
                      {#if selectedAdminDispute.messages.length === 0}
                        <div class="chat-placeholder">Сообщений пока нет.</div>
                      {:else}
                        {#each selectedAdminDispute.messages as message (message.id)}
                          <div class:admin={isAdminMessage(message)} class:own={isOwnMessage(message)} class="message-row">
                            <div class="message-bubble">
                              {#if isAdminMessage(message)}
                                <span class="message-author-badge">Админ</span>
                              {/if}
                              <p>{message.body}</p>
                              <span class="message-meta">{formatDate(message.sent_at)}</span>
                            </div>
                          </div>
                        {/each}
                      {/if}
                    </div>
                    <form class="chat-compose" on:submit|preventDefault={() => run(submitAdminMessage)}>
                      <input bind:value={chatDraft} maxlength="2000" placeholder="Сообщение участникам спора" />
                      <button class="primary-button compact" type="submit" disabled={loading || !chatDraft.trim()}>Отправить</button>
                    </form>
                  </article>
                  <article class="details-card">
                    <h3>Решение</h3>
                    <textarea bind:value={adminNote} rows="3" placeholder="Комментарий к решению, опционально"></textarea>
                    <div class="modal-actions">
                      <button class="status-button" type="button" disabled={loading} on:click={() => run(() => resolveSelectedDispute("release_to_worker"))}>
                        Выплатить исполнителю
                      </button>
                      <button class="danger-button" type="button" disabled={loading} on:click={() => run(() => resolveSelectedDispute("refund_customer"))}>
                        Вернуть заказчику
                      </button>
                    </div>
                  </article>
                {/if}
              {/if}
            </section>
          {:else if dashboardSection === "settings"}
            <section class="settings-panel">
              <article class="settings-card">
                <div>
                  <p class="eyebrow">Профиль</p>
                  <h2>Контакты и данные</h2>
                </div>
                <form class="settings-form" on:submit|preventDefault={() => run(submitProfileSettings)}>
                  <label>
                    Имя
                    <input bind:value={settingsName} required />
                  </label>
                  <label>
                    Почта
                    <input bind:value={settingsEmail} type="email" required />
                  </label>
                  <label>
                    Телефон
                    <input bind:value={settingsPhone} inputmode="tel" pattern="(?:\+7|8)[0-9\s().-]{10,16}" />
                  </label>
                  {#if isWorker}
                    <label>
                      Город
                      <input bind:value={settingsCity} placeholder="Москва" required />
                    </label>
                  {/if}
                  <button class="status-button" type="submit" disabled={loading}>Сохранить профиль</button>
                </form>
              </article>

              <article class="settings-card">
                <div>
                  <p class="eyebrow">Аватар</p>
                  <h2>Фото профиля</h2>
                </div>
                <div class="avatar-preview">{@render Avatar(settingsAvatarUrl || null)}</div>
                <form class="settings-form" on:submit|preventDefault={() => run(submitAvatarSettings)}>
                  <label
                    class="avatar-dropzone"
                    on:dragover|preventDefault
                    on:drop={(event) => run(() => handleAvatarDrop(event))}
                  >
                    <input accept="image/png,image/jpeg,image/webp" type="file" on:change={(event) => run(() => handleAvatarInput(event))} />
                    <span>Перетащите картинку сюда или выберите с рабочего стола</span>
                    <small>{avatarUploadHint}</small>
                  </label>
                  <button class="status-button" type="submit" disabled={loading}>Обновить аватар</button>
                </form>
              </article>

              <article class="settings-card">
                <div>
                  <p class="eyebrow">Безопасность</p>
                  <h2>Смена пароля</h2>
                </div>
                <form class="settings-form" on:submit|preventDefault={() => run(submitPasswordSettings)}>
                  <label>
                    Текущий пароль
                    <input bind:value={currentPassword} type="password" required />
                  </label>
                  <label>
                    Новый пароль
                    <input bind:value={newPassword} minlength="8" type="password" required />
                  </label>
                  <button class="status-button" type="submit" disabled={loading}>Изменить пароль</button>
                </form>
              </article>

              <article class="settings-card">
                <div>
                  <p class="eyebrow">Паспорт</p>
                  <h2>{currentUser?.identity_status === "verified" ? "Личность подтверждена" : "Подтвердить личность"}</h2>
                </div>
                <form class="settings-form" on:submit|preventDefault={() => run(submitIdentitySettings)}>
                  <label>
                    ФИО как в паспорте
                    <input bind:value={passportFullName} required />
                  </label>
                  <label>
                    Серия и номер паспорта
                    <input bind:value={passportNumber} placeholder="4510 123456" required />
                  </label>
                  <button class="status-button" type="submit" disabled={loading}>Подтвердить по паспорту</button>
                </form>
              </article>
            </section>
          {:else if dashboardSection === "payments"}
            <section class="payments-panel">
              <div class="payment-summary-grid">
                <article class="payment-summary-card">
                  <span>{isWorker ? "Доступно к выводу" : "Оплачено работникам"}</span>
                  <strong>{formatMoney(isWorker ? paymentsDashboard?.wallet.balance_available ?? 0 : getPaymentTotal("released"))}</strong>
                </article>
                <article class="payment-summary-card">
                  <span>{isWorker ? "В резерве по активным заказам" : "Зарезервировано"}</span>
                  <strong>{formatMoney(paymentsDashboard?.hold_total ?? 0)}</strong>
                </article>
                <article class="payment-summary-card">
                  <span>{isWorker ? "Уже выплачено" : "Всего операций"}</span>
                  <strong>{isWorker ? formatMoney(paymentsDashboard?.wallet.balance_paid_out ?? 0) : String(paymentsDashboard?.payments.length ?? 0)}</strong>
                </article>
              </div>
              {#if isWorker}
                <button
                  class="primary-button compact"
                  type="button"
                  disabled={loading || !paymentsDashboard?.wallet.balance_available}
                  on:click={() => run(submitPayoutRequest)}
                >
                  Запросить вывод
                </button>
              {/if}
              <div class="payment-list">
                {#if !paymentsDashboard || paymentsDashboard.payments.length === 0}
                  <article class="payment-row">
                    <strong>Платежей пока нет</strong>
                    <span>История появится после создания и принятия заказов.</span>
                  </article>
                {:else}
                  {#each paymentsDashboard.payments as payment}
                    <article class="payment-row">
                      <div>
                        <strong>{payment.order_title ?? "Задача"}</strong>
                        <span>{formatDate(payment.created_at)} · {paymentStatusLabels[payment.status]} · {getPaymentFeeText(payment)}</span>
                      </div>
                      <b>{formatMoney(isWorker ? payment.worker_amount : payment.amount)}</b>
                    </article>
                  {/each}
                {/if}
              </div>
              {#if isWorker && paymentsDashboard?.payouts.length}
                <div class="payment-list compact-list">
                  {#each paymentsDashboard.payouts as payout}
                    <article class="payment-row">
                      <div>
                        <strong>Выплата</strong>
                        <span>{formatDate(payout.created_at)} · Выплачено</span>
                      </div>
                      <b>{formatMoney(payout.amount)}</b>
                    </article>
                  {/each}
                </div>
              {/if}
            </section>
          {:else if dashboardSection === "messages"}
            <section class="chat-panel">
              {#if chatOrders.length === 0}
                <article class="chat-empty">
                  <p class="eyebrow">Сообщения</p>
                  <h2>Чат откроется после принятия заказа</h2>
                  <p>Переписка доступна только между заказчиком и назначенным работником. После подтверждения завершения заказа чат очищается.</p>
                </article>
              {:else}
                <div class="chat-order-tabs" aria-label="Выбор заказа для чата">
                  {#each chatOrders as order}
                    <button class:active={selectedChatOrder?.id === order.id} type="button" on:click={() => run(() => loadChat(order.id))}>
                      {getOrderTitle(order)}
                    </button>
                  {/each}
                </div>
                <article class="chat-shell">
                  <header class="chat-header">
                    {@render Avatar(getChatPeerAvatar(selectedChatOrder))}
                    <div>
                      <strong>{getChatPeerName(selectedChatOrder)}</strong>
                      <span>{selectedChatOrder ? getStatusLabel(selectedChatOrder) : "Нет активного заказа"}</span>
                    </div>
                  </header>
                  <div class="message-list" aria-live="polite">
                    {#if chatMessages.length === 0}
                      <div class="chat-placeholder">Сообщений пока нет. Напишите первое сообщение по заказу.</div>
                    {:else}
                      {#each chatMessages as message (message.id)}
                        <div class:admin={isAdminMessage(message)} class:own={isOwnMessage(message)} class="message-row">
                          <div class="message-bubble">
                            {#if isAdminMessage(message)}
                              <span class="message-author-badge">Админ</span>
                            {/if}
                            <p>{message.body}</p>
                            <span class="message-meta">
                              {formatDate(message.sent_at)}
                              {#if isOwnMessage(message)}
                                <span class="message-status" aria-label={getMessageStatus(message)}>
                                  {#if getMessageStatus(message) === "clock"}
                                    ◷
                                  {:else if getMessageStatus(message) === "read"}
                                    <span class="double-check">✓✓</span>
                                  {:else}
                                    ✓
                                  {/if}
                                </span>
                              {/if}
                            </span>
                          </div>
                        </div>
                      {/each}
                    {/if}
                  </div>
                  <form class="chat-compose" on:submit|preventDefault={() => run(submitChatMessage)}>
                    <input bind:value={chatDraft} maxlength="2000" placeholder="Написать сообщение" />
                    <button class="primary-button compact" type="submit" disabled={loading || !chatDraft.trim()}>Отправить</button>
                  </form>
                </article>
              {/if}
            </section>
          {:else if dashboardSection === "reviews" && isWorker}
            <section class="reviews-panel">
              <article class="review-summary-card">
                <span>Рейтинг</span>
                <strong>{workerProfile?.rating_count ? workerProfile.rating_avg.toFixed(1) : "0"}</strong>
                <p>{workerProfile?.rating_count ? `${workerProfile.rating_count} отзывов` : "Отзывов пока нет"}</p>
              </article>
              <div class="review-list">
                {#if workerReviews.length === 0}
                  <article class="review-item">
                    <strong>Пока нет отзывов</strong>
                    <p>Отзывы появятся после завершения и оценки заказов.</p>
                  </article>
                {:else}
                  {#each workerReviews as review}
                    <article class="review-item">
                      <div>
                        <strong>{review.order_title ?? "Задача"}</strong>
                        <span>{review.customer_full_name ?? "Заказчик"} · {formatDate(review.created_at)}</span>
                      </div>
                      <b>{"★".repeat(review.score)}{"☆".repeat(5 - review.score)}</b>
                      <p>{review.comment ?? "Без комментария"}</p>
                    </article>
                  {/each}
                {/if}
              </div>
            </section>
          {:else}
          <div class="tabs" aria-label="Фильтр задач">
            <button class:active={activeTab === "active"} type="button" on:click={() => setTaskTab("active")}>Активные</button>
            <button class:active={activeTab === "done"} type="button" on:click={() => setTaskTab("done")}>Завершенные</button>
          </div>
          <div class:done-order-list={activeTab === "done"} class="task-grid task-board">
            {#if !accessToken}
              <article class="task-card">
                <h3>Войдите в аккаунт</h3>
                <p>После входа здесь появятся ваши задачи и уведомления.</p>
                <button class="status-button" type="button" on:click={() => setScreen("login")}>Войти</button>
              </article>
            {:else if visibleOrders.length === 0}
              <article class="task-card">
                <h3>{isWorker ? "Назначенных заказов пока нет" : "Задач пока нет"}</h3>
                <p>
                  {isWorker
                    ? "Выйдите на смену, чтобы увидеть назначенные задачи и забрать ближайший ожидающий заказ."
                    : "Создайте первую задачу, и система назначит свободного исполнителя."}
                </p>
                {#if !isWorker}
                  <button class="status-button" type="button" on:click={() => setScreen("create")}>Создать задачу</button>
                {/if}
              </article>
            {:else}
              {#each visibleOrders as order}
                <article class="task-card">
                  <div class="task-topline">
                    <div>
                      <h3>{getOrderTitle(order)}</h3>
                      <p class="task-meta">{order.address} · {formatDate(order.scheduled_at)} · {formatMoney(order.budget_amount)}</p>
                    </div>
                  </div>
                  {#if isCustomer}
                    <button class="worker-strip worker-strip-button" type="button" disabled={!hasConfirmedWorker(order)} on:click={() => { openOrderDetails(order); workerProfileOpen = true; }}>
                      {@render Avatar(hasConfirmedWorker(order) ? order.worker_avatar_url : null)}
                      <div>
                        <strong>{hasConfirmedWorker(order) ? order.worker_full_name ?? "Исполнитель" : getStatusLabel(order)}</strong>
                        <span class="stars">★★★★★ <b>{hasConfirmedWorker(order) ? getWorkerRating(order) : "0"}</b></span>
                      </div>
                    </button>
                  {/if}
                  <button class="outline-button compact" type="button" on:click={() => openOrderDetails(order)}>Подробнее</button>
                  {#if role === "worker" && order.status === "assigned"}
                    <button class="status-button" type="button" on:click={() => run(() => handleWorkerAction(order, "accept"))}>
                      Принять заказ
                    </button>
                  {:else if role === "worker" && order.status === "accepted"}
                    <button class="status-button" type="button" on:click={() => run(() => handleWorkerAction(order, "start"))}>
                      Начать работу
                    </button>
                  {:else if role === "worker" && order.status === "in_progress"}
                    <button class="status-button" type="button" on:click={() => run(() => handleWorkerAction(order, "complete"))}>
                      Отправить на подтверждение
                    </button>
                  {:else if role === "customer" && order.status === "completion_requested"}
                    <button class="status-button" type="button" on:click={() => run(() => confirmCompletion(order))}>
                      Подтвердить завершение
                    </button>
                  {:else if role === "customer" && order.status === "completed"}
                    <label>
                      Оценка
                      <input bind:value={reviewScore} min="1" max="5" type="number" />
                    </label>
                    <label>
                      Отзыв
                      <input bind:value={reviewComment} />
                    </label>
                    <button class="status-button" type="button" on:click={() => run(() => submitReview(order))}>
                      Оценить работу
                    </button>
                  {:else}
                    <button class="status-button" type="button">{getStatusLabel(order)}</button>
                  {/if}
                </article>
              {/each}
            {/if}
          </div>
          {/if}
          {#if isWorker && dashboardSection === "tasks"}
            <section class="notifications-panel" aria-label="Уведомления работника">
              <div class="notifications-list">
                {#if notifications.length === 0}
                  <article class="notification-card">
                    <strong>Пока пусто</strong>
                    <p>Новые назначения и отзывы появятся здесь.</p>
                  </article>
                {:else}
                  {#each notifications as notification}
                    <article class:unread={!notification.is_read} class="notification-card">
                      <strong>{notification.title}</strong>
                      <p>{notification.body}</p>
                      <span>{formatDate(notification.created_at)}</span>
                    </article>
                  {/each}
                {/if}
              </div>
            </section>
          {/if}
        </section>
      </section>
    {:else}
      <section class="create-page page-section">
        {#if isWorker}
          <div class="create-heading">
            <p class="eyebrow">Доступно заказчикам</p>
            <h1>Работник принимает задачи в кабинете</h1>
            <button class="primary-button" type="button" on:click={() => setScreen("dashboard")}>Открыть кабинет</button>
          </div>
        {:else}
        <div class="create-heading">
          <p class="eyebrow">Новая задача</p>
          <h1>Опишите работу, а TaskNow найдет исполнителя</h1>
        </div>
        <div class="create-grid">
          <form class="task-form" on:submit|preventDefault={() => run(submitTask)}>
            <label>
              Title
              <input bind:value={taskTitle} placeholder="Разгрузить мебель" required />
            </label>
            <label>
              Description
              <textarea bind:value={taskDescription} rows="5" placeholder="Что нужно сделать, какие инструменты нужны, куда подъехать" required></textarea>
            </label>
            <div class="form-row">
              <label>
                Бюджет
                <input bind:value={taskBudget} inputmode="numeric" min="1" placeholder="5000" required type="number" />
              </label>
              <label>
                Category
                <select bind:value={taskCategory}>
                  {#each categories as category}
                    <option>{category}</option>
                  {/each}
                </select>
              </label>
            </div>
            <label>
              Город
              <input bind:value={taskCity} placeholder="Москва" required />
            </label>
            <label>
              Адрес
              <input bind:value={taskLocation} placeholder="Москва, ул. Тверская, 12" required />
            </label>
            <label>
              Time
              <input bind:value={taskScheduledAt} type="datetime-local" required />
            </label>
            <button class="primary-button full large" type="submit" disabled={loading}>Опубликовать задачу</button>
          </form>
          <aside class="map-preview" aria-label="Превью карты">
            <div class="map-line line-one"></div>
            <div class="map-line line-two"></div>
            <div class="map-line line-three"></div>
            <div class="map-pin pin-main"></div>
            <article class="map-card">
              <strong>3 исполнителя рядом</strong>
              <span>Отклик за 2-5 минут</span>
            </article>
          </aside>
        </div>
        {/if}
      </section>
    {/if}
    {#if avatarEditorOpen}
      <div class="modal-backdrop" role="presentation" on:click|self={() => (avatarEditorOpen = false)}>
        <section class="avatar-editor" aria-label="Редактирование аватарки">
          <div class="avatar-editor-copy">
            <p class="eyebrow">Аватар</p>
            <h2>Настройте кадр</h2>
            <p>Перетащите изображение внутри круга и выберите масштаб. Так аватар будет выглядеть в профиле.</p>
          </div>
          <div
            aria-label="Область перемещения аватарки"
            class="avatar-cropper"
            role="application"
            on:pointerdown={startAvatarDrag}
            on:pointermove={moveAvatarDrag}
            on:pointerup={endAvatarDrag}
            on:pointercancel={endAvatarDrag}
          >
            <img
              alt="Предпросмотр аватарки"
              draggable="false"
              src={avatarSourceUrl}
              style={`transform: translate(${avatarOffsetX}px, ${avatarOffsetY}px) scale(${avatarScale});`}
              on:dragstart|preventDefault
            />
          </div>
          <label class="scale-control">
            Масштаб
            <input
              max="2.4"
              min="1"
              step="0.05"
              type="range"
              value={avatarScale}
              on:input={(event) => setAvatarScale(Number((event.currentTarget as HTMLInputElement).value))}
            />
          </label>
          <div class="modal-actions">
            <button class="ghost-button" type="button" on:click={() => (avatarEditorOpen = false)}>Отмена</button>
            <button class="primary-button compact" type="button" on:click={() => run(applyAvatarCrop)}>Применить</button>
          </div>
        </section>
      </div>
    {/if}
    {#if selectedOrder}
      <div class="modal-backdrop" role="presentation" on:click|self={() => (selectedOrder = null)}>
        <section class="order-details" aria-label="Подробности заказа">
          <div class="details-head">
            <div>
              <p class="eyebrow">Заказ</p>
              <h2>{getOrderTitle(selectedOrder)}</h2>
              <span>{getStatusLabel(selectedOrder)} · {formatMoney(selectedOrder.budget_amount)}</span>
            </div>
            <button class="ghost-button" type="button" on:click={() => (selectedOrder = null)}>Закрыть</button>
          </div>
          <div class="details-grid">
            <article class="details-card">
              <h3>Описание задачи</h3>
              <p>{selectedOrder.description}</p>
              <span>{selectedOrder.address}</span>
              <span>{formatDate(selectedOrder.scheduled_at)}</span>
            </article>
            <article class="details-card">
              <h3>Платеж</h3>
              {#if selectedOrderPayment}
                <p>{paymentStatusLabels[selectedOrderPayment.status]}</p>
                <span>Бюджет: {formatMoney(selectedOrderPayment.amount)}</span>
                {#if shouldShowPaymentCommission(selectedOrderPayment)}
                  <span>Комиссия сервиса: {formatMoney(selectedOrderPayment.service_fee)}</span>
                  <span>Работнику: {formatMoney(selectedOrderPayment.worker_amount)}</span>
                {:else}
                  <span>Возврат заказчику без комиссии</span>
                {/if}
              {:else}
                <p>Платеж еще не создан</p>
              {/if}
            </article>
          </div>
          {#if hasConfirmedWorker(selectedOrder)}
            <article class="details-card worker-profile-card">
              <button class="worker-strip worker-strip-button" type="button" on:click={() => (workerProfileOpen = !workerProfileOpen)}>
                {@render Avatar(selectedOrder.worker_avatar_url)}
                <div>
                  <strong>{selectedOrder.worker_full_name ?? "Исполнитель"}</strong>
                  <span>★ {getWorkerRating(selectedOrder)} · {selectedOrder.worker_rating_count ?? 0} отзывов</span>
                </div>
              </button>
              {#if workerProfileOpen}
                <p>Профиль исполнителя подтвержден в системе. Рейтинг формируется по завершенным заказам и отзывам заказчиков.</p>
              {/if}
            </article>
          {/if}
          <article class="details-card">
            <h3>История статусов</h3>
            <div class="timeline">
              {#each getTimeline(selectedOrder) as item}
                <div class="timeline-item">
                  <span></span>
                  <div>
                    <strong>{item.label}</strong>
                    <small>{formatDate(item.date)}</small>
                  </div>
                </div>
              {/each}
            </div>
          </article>
          {#if ["accepted", "in_progress", "completion_requested"].includes(selectedOrder.status)}
            <button class="danger-button" type="button" disabled={loading} on:click={() => run(() => openDispute(selectedOrder!))}>
              Открыть спор
            </button>
          {/if}
        </section>
      </div>
    {/if}
    <footer class="site-footer">
      <span>© 2026 52GAP67</span>
      <span>TaskNow · подбор исполнителей для срочных задач</span>
    </footer>
  </section>
</main>

{#snippet Avatar(src: string | null)}
  <svg class="avatar-icon" viewBox="0 0 48 48" aria-hidden="true">
    {#if src}
      <image href={src} x="0" y="0" width="48" height="48" preserveAspectRatio="xMidYMid slice" />
    {:else}
      <circle cx="24" cy="24" r="23" />
      <circle class="avatar-head" cx="24" cy="18" r="8" />
      <path class="avatar-body" d="M10 40c2.4-8 7.2-12 14-12s11.6 4 14 12" />
    {/if}
  </svg>
{/snippet}

{#snippet Icon(name: "edit" | "route" | "star" | "list" | "wallet" | "message" | "settings")}
  <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
    {#if name === "edit"}
      <path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3Z" />
      <path d="m14 8 2 2" />
    {:else if name === "route"}
      <path d="M6 18c4 0 2-12 7-12h5" />
      <path d="m15 3 3 3-3 3" />
      <circle cx="6" cy="18" r="2" />
    {:else if name === "star"}
      <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-2.9-5.5 2.9 1-6.2L3 9.6l6.2-.9L12 3Z" />
    {:else if name === "wallet"}
      <path d="M4 7h14a2 2 0 0 1 2 2v9H6a2 2 0 0 1-2-2V7Z" />
      <path d="M16 13h4" />
      <path d="M6 7V5h11" />
    {:else if name === "message"}
      <path d="M5 5h14v10H8l-3 3V5Z" />
      <path d="M8 9h8M8 12h5" />
    {:else if name === "settings"}
      <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
      <path d="M4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4" />
    {:else}
      <path d="M5 6h14M5 12h14M5 18h14" />
    {/if}
  </svg>
{/snippet}
