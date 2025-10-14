import React from 'react';
import { User, Copy } from 'lucide-react';
import { toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import BotLogo from '/src/assets/images/logo.svg';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import DOMPurify from 'dompurify';

interface Message {
  id: string;
  text: string;
  isBot: boolean;
  timestamp: Date;
  isError?: boolean;
  references?: string[];
  query_type?: string;
  needs_clarification?: boolean;
}

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const {
    text,
    isBot,
    timestamp,
    isError = false,
    references = [],
    query_type = 'general_inquiry',
    needs_clarification = false,
  } = message;

  const responseTypeConfig: Record<string, { bgColor: string; borderColor: string }> = {
    greeting: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    policy_summary: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200'},
    similar_search: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    specific_person: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    comparison: {  bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    coverage_check: {bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    limits_deductibles: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    open_ended: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    general_inquiry: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    no_results: {bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    non_insurance: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
    error: { bgColor: 'bg-red-50', borderColor: 'border-red-200' },
    personal_claim: { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' },
  };

  const currentConfig = responseTypeConfig[query_type] || responseTypeConfig.general_inquiry;

  const processMarkdown = (markdown: string): string => {
    // Sanitize input to prevent XSS
    let sanitizedMarkdown = DOMPurify.sanitize(markdown, {
      ALLOWED_TAGS: ['p', 'strong', 'em', 'ul', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'br'],
      ALLOWED_ATTR: [],
    });

    // Removed <br> replacement to prevent breaking table rows

    // Removed bullet point replacement to avoid inconsistent replacements; keep original • for consistency with screenshot

    // Ensure proper formatting for coverage sections
    sanitizedMarkdown = sanitizedMarkdown.replace(/\*\*WHAT'S COVERED:\*\*\n/g, '**WHAT\'S COVERED:**\n');
    sanitizedMarkdown = sanitizedMarkdown.replace(/\*\*WHAT'S NOT COVERED:\*\*\n/g, '**WHAT\'S NOT COVERED:**\n');

    // Append references if any
    if (references.length > 0) {
      sanitizedMarkdown += '\n\n**References:**\n' + references.map(r => r.replace(/\*\*/g, '')).join('\n');
    }

    return sanitizedMarkdown;
  };

  const processedText = processMarkdown(text);

  const handleCopy = async () => {
    try {
      // Copy plain text by stripping markdown and table pipes
      const plainText = processedText
        .replace(/(\*\*|__)(.*?)\1/g, '$2') // Bold marks
        .replace(/^\|.*\|$/gm, (row) => row.replace(/\|/g, ' ').trim()) // Flatten table rows
        .replace(/\n{2,}/g, '\n') // Collapse multiple new lines
        .replace(/-\s/g, '') // Remove list markers
        .trim();

      await navigator.clipboard.writeText(plainText);
      toast.success('Text copied to clipboard!', { position: 'top-right', autoClose: 3000 });
    } catch (e) {
      console.error('Copy failed', e);
      toast.error('Failed to copy text.', { position: 'top-right', autoClose: 3000 });
    }
  };

  return (
    <div className={`flex ${isBot ? 'justify-start' : 'justify-end'} mb-4 animate-fade-in`}>
      <div className={`flex max-w-[70%] ${isBot ? 'flex-row' : 'flex-row-reverse'} items-end space-x-2`}>
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isBot ? 'text-gray-600' : 'bg-gray-100 text-gray-600'
          }`}
        >
          {isBot ? <img src={BotLogo} alt="Bot Logo" className="w-4 h-4" /> : <User className="w-4 h-4" />}
        </div>
        <div className={`${isBot ? 'ml-2' : 'mr-2'} flex flex-col w-full`}>
          <div
            className={`px-4 py-3 rounded-2xl shadow-sm border relative ${
              isError
                ? 'border-red-300 bg-red-50'
                : `${currentConfig.bgColor} ${currentConfig.borderColor}`
            } text-gray-800 ${isBot ? 'rounded-bl-sm rounded-tl-none' : 'rounded-br-sm'}`}
          >
            {needs_clarification && (
              <div className="mb-2 p-2 bg-yellow-100 border border-yellow-300 rounded text-sm text-yellow-800">
                <strong>Clarification Needed:</strong> Please provide more details to refine your query.
              </div>
            )}
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                table: ({ children }) => <table className="w-full border-collapse border border-gray-300 my-4">{children}</table>,
                thead: ({ children }) => <thead className="bg-gray-100">{children}</thead>,
                th: ({ children }) => (
                  <th className="border border-gray-300 px-4 py-2 text-left font-semibold">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="border border-gray-300 px-4 py-2 align-top whitespace-pre-wrap">{children}</td>
                ),
                ul: ({ children }) => <ul className="list-disc pl-5">{children}</ul>,
                li: ({ children }) => <li className="my-1">{children}</li>,
                strong: ({ children }) => <strong>{children}</strong>,
                p: ({ children }) => <p className="my-2">{children}</p>,
              }}
            >
              {processedText}
            </ReactMarkdown>
          </div>
          <div className="flex justify-between w-full mt-1">
            <span className="text-xs text-gray-500">{timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            {isBot && (
              <button onClick={handleCopy} className="text-gray-500 hover:text-gray-700" title="Copy message">
                <Copy className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;