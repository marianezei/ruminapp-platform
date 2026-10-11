import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { parseHTML } from 'k6/html';

const BASE = __ENV.TARGET_URL || 'http://web.ruminapp.svc:8080';
const USER = __ENV.LOADGEN_USER;
const PASSWORD = __ENV.LOADGEN_PASSWORD;
const WRITE_RATIO = Number(__ENV.WRITE_RATIO || '0.05');

export const options = {
  noVUConnectionReuse: true,
  scenarios: {
    browsing: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || '4'),
      duration: __ENV.DURATION || '87600h',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

function csrf(res) {
  return parseHTML(res.body).find('input[name=csrfmiddlewaretoken]').attr('value');
}

function login() {
  const page = http.get(`${BASE}/entrar/`, { tags: { name: 'login' } });
  const res = http.post(`${BASE}/entrar/`, {
    csrfmiddlewaretoken: csrf(page),
    username: USER,
    password: PASSWORD,
  }, { headers: { Referer: `${BASE}/entrar/` }, tags: { name: 'login' } });
  check(res, { 'logged in': (r) => r.status === 200 && r.url.indexOf('/entrar/') === -1 });
}

function animalIds(res) {
  const ids = [];
  parseHTML(res.body).find('a[href^="/animais/"]').each((_, el) => {
    const m = el.getAttribute('href').match(/^\/animais\/(\d+)\/$/);
    if (m) ids.push(m[1]);
  });
  return ids;
}

const FILTERS = ['', '?categoria=LACTACAO', '?situacao=PRENHE', '?ordem=dias', '?categoria=SECA&ordem=nome',
  '?situacao=VAZIA&dias_min=60', '?q=1'];

export default function () {
  if (http.cookieJar().cookiesForURL(BASE).sessionid === undefined) {
    login();
  }

  group('dashboard', () => {
    check(http.get(`${BASE}/`, { tags: { name: 'painel' } }), { 'dashboard 200': (r) => r.status === 200 });
  });
  sleep(Math.random() * 2);

  let ids = [];
  group('list', () => {
    const filter = FILTERS[Math.floor(Math.random() * FILTERS.length)];
    const res = http.get(`${BASE}/animais/${filter}`, { tags: { name: 'animal_lista' } });
    check(res, { 'list 200': (r) => r.status === 200 });
    ids = animalIds(res);
  });
  sleep(Math.random() * 2);

  if (ids.length) {
    const id = ids[Math.floor(Math.random() * ids.length)];
    group('detail', () => {
      const res = http.get(`${BASE}/animais/${id}/`, { tags: { name: 'animal_detalhe' } });
      check(res, { 'detail 200': (r) => r.status === 200 });

      if (Math.random() < WRITE_RATIO) {
        const today = new Date().toISOString().slice(0, 10);
        const event = http.post(`${BASE}/eventos/novo/`, {
          csrfmiddlewaretoken: csrf(res), animal: id, tipo: 'CIO', data: today, proximo: 'animal',
        }, { headers: { Referer: `${BASE}/animais/${id}/` }, tags: { name: 'evento_novo' } });
        check(event, { 'event accepted': (r) => r.status === 200 });
      }
    });
  }
  sleep(1 + Math.random() * 3);
}
