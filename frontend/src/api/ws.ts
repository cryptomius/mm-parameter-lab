import type { WsMessage } from "../types/messages";

export type WsHandler = (msg: WsMessage) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private handlers = new Set<WsHandler>();

  connect(url: string = "/ws"): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}${url}`);
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WsMessage;
        this.handlers.forEach((h) => h(msg));
      } catch {
        // ignore non-json (errors)
      }
    };
    this.ws.onclose = () => {
      this.ws = null;
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  subscribe(h: WsHandler): () => void {
    this.handlers.add(h);
    return () => this.handlers.delete(h);
  }
}

export const wsClient = new WsClient();
