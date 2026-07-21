export function byId<T extends HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

export function bySel<T extends Element>(sel: string, parent?: Element): T | null {
  return (parent || document).querySelector<T>(sel);
}

export function byAll<T extends Element>(sel: string, parent?: Element): NodeListOf<T> {
  return (parent || document).querySelectorAll<T>(sel);
}

export function esc(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function ts(): string {
  return new Date().toLocaleTimeString('it', { hour: '2-digit', minute: '2-digit' });
}

export function tsfull(): string {
  return new Date().toLocaleTimeString('it', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}
