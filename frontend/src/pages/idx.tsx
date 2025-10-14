import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, FileText, AlertCircle } from 'lucide-react';
import ChatMessage from '../components/ChatMessage';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import TypingIndicator from '../components/TypingIndicator';
import backgroundImage from '../assets/images/5166950.jpg';
import logoImage from '../assets/images/lg.png';
import debounce from 'lodash/debounce';

interface Message {
  id: string;
  text: string;
  isBot: boolean;
  timestamp: Date;
  isError?: boolean;
  references?: string[];
  query_type?: string;
  format_used?: string;
  needs_clarification?: boolean;
}

const Index: React.FC = () => {
  const initialMessageText = "Hello! I'm your document intelligence agent. How can I help you with your insurance queries today?";
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: initialMessageText,
      isBot: true,
      timestamp: new Date(),
      isError: false,
      references: [],
      query_type: 'greeting',
      format_used: 'text',
      needs_clarification: false,
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/local_test';

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, scrollToBottom]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea && document.activeElement !== textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [inputText]);

  const addMessage = (
    text: string,
    isBot: boolean,
    isError: boolean = false,
    references: string[] = [],
    query_type: string = 'general_inquiry',
    format_used: string = 'mandatory_table',
    needs_clarification: boolean = false
  ) => {
    const newMessage: Message = {
      id: Date.now().toString(),
      text,
      isBot,
      timestamp: new Date(),
      isError,
      references,
      query_type,
      format_used,
      needs_clarification,
    };
    setMessages((prev) => [...prev, newMessage]);
  };

  const handleSendMessage = useCallback(
    debounce(async () => {
      if (!inputText.trim()) return;

      addMessage(inputText, false);
      setInputText('');
      setIsTyping(true);
      setError(null);

      try {
        const response = await fetch(API_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({
            query: inputText,
            session_id: sessionId || undefined,
          }),
        });

        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}.`);
        }

        const data = await response.json();
        console.log('Backend Response:', data);
        setIsTyping(false);

        if (data.error) {
          addMessage(`Error: ${data.error}`, true, true, [], 'error', 'text', false);
          setError(data.error);
          return;
        }

        const { answer, query_type, format_used, needs_clarification, session_id } = data;
        const references = data.references || [];

        if (session_id && !sessionId) {
          setSessionId(session_id);
        }

        addMessage(
          answer,
          true,
          false,
          references,
          query_type || 'general_inquiry',
          format_used || 'mandatory_table',
          needs_clarification || false
        );
      } catch (error) {
        setIsTyping(false);
        const errorMsg = error instanceof Error ? error.message : 'Network error occurred.';
        addMessage(`Error: ${errorMsg}`, true, true, [], 'error', 'text', false);
        setError(`Failed to connect to the server at ${API_URL}. Please check if the backend is running.`);
      }
    }, 300),
    [inputText, sessionId]
  );

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div
      style={{
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
      className="h-screen w-screen relative overflow-hidden"
    >
      <div className="absolute inset-0">
        <div className="absolute top-0 left-0 w-96 h-96 bg-gradient-to-br from-blue-400/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute top-20 right-0 w-80 h-80 bg-gradient-to-br from-purple-400/15 to-indigo-500/15 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-gradient-to-br from-teal-400/10 to-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '4s' }}></div>
        <div className="absolute bottom-20 right-1/4 w-64 h-64 bg-gradient-to-br from-indigo-400/15 to-purple-500/15 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        <div className="absolute top-1/3 left-1/2 w-48 h-48 bg-gradient-to-br from-cyan-300/8 to-blue-400/8 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '3s' }}></div>
        <div className="absolute bottom-1/3 right-1/3 w-56 h-56 bg-gradient-to-br from-purple-300/10 to-indigo-400/10 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '5s' }}></div>
      </div>

      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px]"></div>
      <div className="absolute inset-0 bg-[linear-gradient(45deg,rgba(255,255,255,0.01)_25%,transparent_25%,transparent_75%,rgba(255,255,255,0.01)_75%)] bg-[size:40px_40px]"></div>
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/4 w-px h-full bg-gradient-to-b from-transparent via-blue-300/10 to-transparent transform rotate-12"></div>
        <div className="absolute top-0 right-1/3 w-px h-full bg-gradient-to-b from-transparent via-purple-300/8 to-transparent transform -rotate-12"></div>
        <div className="absolute top-0 left-2/3 w-px h-full bg-gradient-to-b from-transparent via-cyan-300/6 to-transparent transform rotate-6"></div>
      </div>

      <div className="h-full flex items-center justify-center p-4 relative z-10">
        <div className="w-full max-w-5xl h-full max-h-[95vh] bg-white/95 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/20 flex flex-col overflow-hidden">
          <div className="bg-gradient-to-r from-slate-800 via-slate-700 to-slate-800 text-white p-6 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 via-blue-600/20 to-cyan-600/20"></div>
            <div className="relative flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 bg-white/10 backdrop-blur-sm rounded-xl flex items-center justify-center border border-white/20 shadow-lg">
                  <FileText className="w-6 h-6 text-cyan-300" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-200 bg-clip-text text-transparent">
                    Insurance Claims Intelligence Agent
                  </h1>
                  <p className="text-slate-300 text-sm mt-1 font-medium">
                    AI-powered insurance policy analysis
                  </p>
                </div>
              </div>
              <div className="flex items-center">
                <img src={logoImage} alt="Logo" className="h-8 w-auto" />
              </div>
            </div>
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-gradient-to-br from-cyan-400/10 to-blue-500/10 rounded-full blur-xl"></div>
            <div className="absolute -left-4 -bottom-4 w-20 h-20 bg-gradient-to-br from-purple-400/10 to-pink-500/10 rounded-full blur-xl"></div>
          </div>

          {error && (
            <div className="p-4 bg-red-100/80 text-red-700 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
              </div>
              <button
                onClick={() => setError(null)}
                className="text-red-700 hover:text-red-900"
              >
                Dismiss
              </button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gradient-to-b from-gray-50/50 to-white/50 backdrop-blur-sm min-h-0">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-gray-200/50 p-6 bg-white/80 backdrop-blur-sm">
            <div className="flex items-center space-x-4">
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your insurance question here..."
                  className="w-full resize-none border border-gray-300/50 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:border-transparent transition-all duration-200 max-h-32 min-h-[48px] text-black placeholder-gray-400"
                  rows={1}
                />
              </div>
              <button
                onClick={handleSendMessage}
                disabled={!inputText.trim() || isTyping}
                className={`bg-black hover:bg-gray-800 disabled:bg-gray-600 text-white p-3 rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 shadow-lg ${
                  isTyping ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
      <ToastContainer
        position="top-right"
        autoClose={3000}
        hideProgressBar={false}
        closeOnClick
        pauseOnHover
      />
    </div>
  );
};

export default Index;