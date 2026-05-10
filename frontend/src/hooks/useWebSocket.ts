import { useEffect, useState, useRef } from 'react';
import { WS_URL } from '@/lib/api';

export function useWebSocket(path: string | null) {
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!path) return;

    const url = `${WS_URL}${path}`;
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      console.log(`Connected to WS: ${url}`);
      setIsConnected(true);
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
      } catch (e) {
        console.error('Failed to parse WS message', event.data);
      }
    };

    ws.current.onclose = () => {
      console.log(`Disconnected from WS: ${url}`);
      setIsConnected(false);
      // Basic reconnect logic could go here
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [path]);

  const sendMessage = (msg: object) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    } else {
      console.error('WebSocket is not open. Cannot send message.');
    }
  };

  return { lastMessage, isConnected, sendMessage };
}
