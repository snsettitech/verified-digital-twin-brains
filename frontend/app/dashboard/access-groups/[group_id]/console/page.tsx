'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function GroupConsolePage() {
  const params = useParams();
  const router = useRouter();
  const groupId = params.group_id as string;
  
  const [group, setGroup] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [twinId, setTwinId] = useState<string>('');

  useEffect(() => {
    fetchGroupInfo();
  }, [groupId]);

  const fetchGroupInfo = async () => {
    try {
      const response = await fetch(`http://localhost:8000/access-groups/${groupId}`, {
        headers: { 'Authorization': 'Bearer development_token' }
      });
      if (response.ok) {
        const data = await response.json();
        setGroup(data);
        setTwinId(data.twin_id);
      }
    } catch (error) {
      console.error('Error fetching group info:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !twinId) return;
    
    const userMessage: Message = { role: 'user', content: inputMessage };
    setMessages([...messages, userMessage]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await fetch(`http://localhost:8000/chat/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: inputMessage,
          group_id: groupId
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      // Handle streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';
      let conversationId = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n').filter(line => line.trim());

          for (const line of lines) {
            try {
              const data = JSON.parse(line);
              if (data.type === 'content') {
                assistantMessage += data.content;
                // Update the last message in real-time
                setMessages([...messages, userMessage, { role: 'assistant', content: assistantMessage }]);
              } else if (data.type === 'metadata') {
                conversationId = data.conversation_id;
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }

      // Final message
      setMessages([...messages, userMessage, { role: 'assistant', content: assistantMessage }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages([...messages, userMessage, { role: 'assistant', content: 'Error: Failed to get response' }]);
    } finally {
      setLoading(false);
    }
  };

  if (!group) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="p-8 h-screen flex flex-col">
      <div className="mb-4">
        <button
          onClick={() => router.back()}
          className="text-blue-600 hover:underline mb-2"
        >
          ← Back to Groups
        </button>
        <h1 className="text-3xl font-bold">Group Console</h1>
        <p className="text-gray-600 mt-2">
          Testing as group: <span className="font-semibold">{group.name}</span>
        </p>
        <p className="text-sm text-gray-500 mt-1">
          This console simulates a conversation as this group to test group-specific responses.
        </p>
      </div>

      <div className="flex-1 border border-gray-200 rounded-lg p-4 mb-4 overflow-y-auto bg-gray-50">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            Start a conversation to test the group's knowledge access
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-3xl px-4 py-2 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white border border-gray-200'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && !loading && handleSendMessage()}
          placeholder="Type your message..."
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <button
          onClick={handleSendMessage}
          disabled={loading || !inputMessage.trim()}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
