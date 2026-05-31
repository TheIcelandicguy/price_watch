function t(t,e,i,r){var s,n=arguments.length,o=n<3?e:null===r?r=Object.getOwnPropertyDescriptor(e,i):r;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(t,e,i,r);else for(var a=t.length-1;a>=0;a--)(s=t[a])&&(o=(n<3?s(o):n>3?s(e,i,o):s(e,i))||o);return n>3&&o&&Object.defineProperty(e,i,o),o}"function"==typeof SuppressedError&&SuppressedError;const e=globalThis,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,r=Symbol(),s=new WeakMap;let n=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==r)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=s.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&s.set(e,t))}return t}toString(){return this.cssText}};const o=(t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,r)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[r+1],t[0]);return new n(i,t,r)},a=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,r))(e)})(t):t,{is:l,defineProperty:c,getOwnPropertyDescriptor:d,getOwnPropertyNames:p,getOwnPropertySymbols:h,getPrototypeOf:u}=Object,g=globalThis,_=g.trustedTypes,f=_?_.emptyScript:"",y=g.reactiveElementPolyfillSupport,m=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?f:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},$=(t,e)=>!l(t,e),b={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:$};Symbol.metadata??=Symbol("metadata"),g.litPropertyMetadata??=new WeakMap;let x=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=b){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),r=this.getPropertyDescriptor(t,i,e);void 0!==r&&c(this.prototype,t,r)}}static getPropertyDescriptor(t,e,i){const{get:r,set:s}=d(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:r,set(e){const n=r?.call(this);s?.call(this,e),this.requestUpdate(t,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??b}static _$Ei(){if(this.hasOwnProperty(m("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(m("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m("properties"))){const t=this.properties,e=[...p(t),...h(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(a(t))}else void 0!==t&&e.push(a(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((t,r)=>{if(i)t.adoptedStyleSheets=r.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const i of r){const r=document.createElement("style"),s=e.litNonce;void 0!==s&&r.setAttribute("nonce",s),r.textContent=i.cssText,t.appendChild(r)}})(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),r=this.constructor._$Eu(t,i);if(void 0!==r&&!0===i.reflect){const s=(void 0!==i.converter?.toAttribute?i.converter:v).toAttribute(e,i.type);this._$Em=t,null==s?this.removeAttribute(r):this.setAttribute(r,s),this._$Em=null}}_$AK(t,e){const i=this.constructor,r=i._$Eh.get(t);if(void 0!==r&&this._$Em!==r){const t=i.getPropertyOptions(r),s="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=r;const n=s.fromAttribute(e,t.type);this[r]=n??this._$Ej?.get(r)??n,this._$Em=null}}requestUpdate(t,e,i,r=!1,s){if(void 0!==t){const n=this.constructor;if(!1===r&&(s=this[t]),i??=n.getPropertyOptions(t),!((i.hasChanged??$)(s,e)||i.useDefault&&i.reflect&&s===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:r,wrapped:s},n){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),!0!==s||void 0!==n)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===r&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,r=this[e];!0!==t||this._$AL.has(e)||void 0===r||this.C(e,void 0,i,r)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};x.elementStyles=[],x.shadowRootOptions={mode:"open"},x[m("elementProperties")]=new Map,x[m("finalized")]=new Map,y?.({ReactiveElement:x}),(g.reactiveElementVersions??=[]).push("2.1.2");const w=globalThis,k=t=>t,A=w.trustedTypes,S=A?A.createPolicy("lit-html",{createHTML:t=>t}):void 0,E="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,C="?"+P,R=`<${C}>`,I=document,U=()=>I.createComment(""),N=t=>null===t||"object"!=typeof t&&"function"!=typeof t,M=Array.isArray,O="[ \t\n\f\r]",z=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,T=/-->/g,H=/>/g,L=RegExp(`>|${O}(?:([^\\s"'>=/]+)(${O}*=${O}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),D=/'/g,j=/"/g,B=/^(?:script|style|textarea|title)$/i,F=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),q=Symbol.for("lit-noChange"),K=Symbol.for("lit-nothing"),V=new WeakMap,W=I.createTreeWalker(I,129);function Y(t,e){if(!M(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==S?S.createHTML(e):e}const G=(t,e)=>{const i=t.length-1,r=[];let s,n=2===e?"<svg>":3===e?"<math>":"",o=z;for(let e=0;e<i;e++){const i=t[e];let a,l,c=-1,d=0;for(;d<i.length&&(o.lastIndex=d,l=o.exec(i),null!==l);)d=o.lastIndex,o===z?"!--"===l[1]?o=T:void 0!==l[1]?o=H:void 0!==l[2]?(B.test(l[2])&&(s=RegExp("</"+l[2],"g")),o=L):void 0!==l[3]&&(o=L):o===L?">"===l[0]?(o=s??z,c=-1):void 0===l[1]?c=-2:(c=o.lastIndex-l[2].length,a=l[1],o=void 0===l[3]?L:'"'===l[3]?j:D):o===j||o===D?o=L:o===T||o===H?o=z:(o=L,s=void 0);const p=o===L&&t[e+1].startsWith("/>")?" ":"";n+=o===z?i+R:c>=0?(r.push(a),i.slice(0,c)+E+i.slice(c)+P+p):i+P+(-2===c?e:p)}return[Y(t,n+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),r]};class J{constructor({strings:t,_$litType$:e},i){let r;this.parts=[];let s=0,n=0;const o=t.length-1,a=this.parts,[l,c]=G(t,e);if(this.el=J.createElement(l,i),W.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(r=W.nextNode())&&a.length<o;){if(1===r.nodeType){if(r.hasAttributes())for(const t of r.getAttributeNames())if(t.endsWith(E)){const e=c[n++],i=r.getAttribute(t).split(P),o=/([.?@])?(.*)/.exec(e);a.push({type:1,index:s,name:o[2],strings:i,ctor:"."===o[1]?et:"?"===o[1]?it:"@"===o[1]?rt:tt}),r.removeAttribute(t)}else t.startsWith(P)&&(a.push({type:6,index:s}),r.removeAttribute(t));if(B.test(r.tagName)){const t=r.textContent.split(P),e=t.length-1;if(e>0){r.textContent=A?A.emptyScript:"";for(let i=0;i<e;i++)r.append(t[i],U()),W.nextNode(),a.push({type:2,index:++s});r.append(t[e],U())}}}else if(8===r.nodeType)if(r.data===C)a.push({type:2,index:s});else{let t=-1;for(;-1!==(t=r.data.indexOf(P,t+1));)a.push({type:7,index:s}),t+=P.length-1}s++}}static createElement(t,e){const i=I.createElement("template");return i.innerHTML=t,i}}function Z(t,e,i=t,r){if(e===q)return e;let s=void 0!==r?i._$Co?.[r]:i._$Cl;const n=N(e)?void 0:e._$litDirective$;return s?.constructor!==n&&(s?._$AO?.(!1),void 0===n?s=void 0:(s=new n(t),s._$AT(t,i,r)),void 0!==r?(i._$Co??=[])[r]=s:i._$Cl=s),void 0!==s&&(e=Z(t,s._$AS(t,e.values),s,r)),e}class Q{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,r=(t?.creationScope??I).importNode(e,!0);W.currentNode=r;let s=W.nextNode(),n=0,o=0,a=i[0];for(;void 0!==a;){if(n===a.index){let e;2===a.type?e=new X(s,s.nextSibling,this,t):1===a.type?e=new a.ctor(s,a.name,a.strings,this,t):6===a.type&&(e=new st(s,this,t)),this._$AV.push(e),a=i[++o]}n!==a?.index&&(s=W.nextNode(),n++)}return W.currentNode=I,r}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,r){this.type=2,this._$AH=K,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Z(this,t,e),N(t)?t===K||null==t||""===t?(this._$AH!==K&&this._$AR(),this._$AH=K):t!==this._$AH&&t!==q&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>M(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==K&&N(this._$AH)?this._$AA.nextSibling.data=t:this.T(I.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,r="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=J.createElement(Y(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(e);else{const t=new Q(r,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=V.get(t.strings);return void 0===e&&V.set(t.strings,e=new J(t)),e}k(t){M(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,r=0;for(const s of t)r===e.length?e.push(i=new X(this.O(U()),this.O(U()),this,this.options)):i=e[r],i._$AI(s),r++;r<e.length&&(this._$AR(i&&i._$AB.nextSibling,r),e.length=r)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=k(t).nextSibling;k(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class tt{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,r,s){this.type=1,this._$AH=K,this._$AN=void 0,this.element=t,this.name=e,this._$AM=r,this.options=s,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=K}_$AI(t,e=this,i,r){const s=this.strings;let n=!1;if(void 0===s)t=Z(this,t,e,0),n=!N(t)||t!==this._$AH&&t!==q,n&&(this._$AH=t);else{const r=t;let o,a;for(t=s[0],o=0;o<s.length-1;o++)a=Z(this,r[i+o],e,o),a===q&&(a=this._$AH[o]),n||=!N(a)||a!==this._$AH[o],a===K?t=K:t!==K&&(t+=(a??"")+s[o+1]),this._$AH[o]=a}n&&!r&&this.j(t)}j(t){t===K?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class et extends tt{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===K?void 0:t}}class it extends tt{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==K)}}class rt extends tt{constructor(t,e,i,r,s){super(t,e,i,r,s),this.type=5}_$AI(t,e=this){if((t=Z(this,t,e,0)??K)===q)return;const i=this._$AH,r=t===K&&i!==K||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,s=t!==K&&(i===K||r);r&&this.element.removeEventListener(this.name,this,i),s&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class st{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){Z(this,t)}}const nt=w.litHtmlPolyfillSupport;nt?.(J,X),(w.litHtmlVersions??=[]).push("3.3.3");const ot=globalThis;class at extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const r=i?.renderBefore??e;let s=r._$litPart$;if(void 0===s){const t=i?.renderBefore??null;r._$litPart$=s=new X(e.insertBefore(U(),t),t,void 0,i??{})}return s._$AI(t),s})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return q}}at._$litElement$=!0,at.finalized=!0,ot.litElementHydrateSupport?.({LitElement:at});const lt=ot.litElementPolyfillSupport;lt?.({LitElement:at}),(ot.litElementVersions??=[]).push("4.2.2");const ct=t=>(e,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(t,e)}):customElements.define(t,e)},dt={attribute:!0,type:String,converter:v,reflect:!1,hasChanged:$},pt=(t=dt,e,i)=>{const{kind:r,metadata:s}=i;let n=globalThis.litPropertyMetadata.get(s);if(void 0===n&&globalThis.litPropertyMetadata.set(s,n=new Map),"setter"===r&&((t=Object.create(t)).wrapped=!0),n.set(i.name,t),"accessor"===r){const{name:r}=i;return{set(i){const s=e.get.call(this);e.set.call(this,i),this.requestUpdate(r,s,t,!0,i)},init(e){return void 0!==e&&this.C(r,void 0,t,e),e}}}if("setter"===r){const{name:r}=i;return function(i){const s=this[r];e.call(this,i),this.requestUpdate(r,s,t,!0,i)}}throw Error("Unsupported decorator location: "+r)};function ht(t){return(e,i)=>"object"==typeof i?pt(t,e,i):((t,e,i)=>{const r=e.hasOwnProperty(i);return e.constructor.createProperty(i,t),r?Object.getOwnPropertyDescriptor(e,i):void 0})(t,e,i)}function ut(t){return ht({...t,state:!0,attribute:!1})}function gt(t){if(null==t||"unknown"===t||"unavailable"===t)return null;const e=Number(t);return Number.isFinite(e)?e:null}function _t(t){return null==t||"unknown"===t||"unavailable"===t?null:"on"===t||"true"===t||"off"!==t&&"false"!==t&&null}function ft(t,e,i="en"){if(null==t)return"—";if(!e)return t.toLocaleString(i);try{return new Intl.NumberFormat(i,{style:"currency",currency:e,maximumFractionDigits:2}).format(t)}catch{return`${t.toLocaleString(i,{maximumFractionDigits:2})} ${e}`}}function yt(t,e="en"){if(!t)return"never";const i=new Date(t).getTime();if(Number.isNaN(i))return t;const r=Date.now()-i,s=Math.round(r/1e3),n=Math.abs(s),o=new Intl.RelativeTimeFormat(e,{numeric:"auto"});return n<60?o.format(-s,"second"):n<3600?o.format(-Math.round(s/60),"minute"):n<86400?o.format(-Math.round(s/3600),"hour"):n<2592e3?o.format(-Math.round(s/86400),"day"):o.format(-Math.round(s/2592e3),"month")}function mt(t){if(!Array.isArray(t))return[];const e=[];for(const i of t)if(null!=i&&"object"==typeof i&&"price"in i&&"ts"in i){const t=i,r="number"==typeof t.price?t.price:null;if(null==r)continue;e.push({ts:String(t.ts??""),price:r,currency:String(t.currency??""),in_stock:!1!==t.in_stock})}return e}function vt(t){if(!Array.isArray(t))return[];const e=[];for(const i of t){if(!i||"object"!=typeof i)continue;const t=i,r="string"==typeof t.title?t.title:"",s="string"==typeof t.url?t.url:"";r&&s&&e.push({title:r,url:s,price:"number"==typeof t.price?t.price:null,currency:"string"==typeof t.currency?t.currency:"",retailer:"string"==typeof t.retailer?t.retailer:"",imageUrl:"string"==typeof t.image_url&&t.image_url?t.image_url:null,confidence:"number"==typeof t.confidence?Math.max(0,Math.min(1,t.confidence)):0,notes:"string"==typeof t.notes?t.notes:"",shipsToUserRegion:"boolean"==typeof t.ships_to_user_region?t.ships_to_user_region:null})}return e.sort((t,e)=>{if(e.confidence!==t.confidence)return e.confidence-t.confidence;return(t.price??Number.POSITIVE_INFINITY)-(e.price??Number.POSITIVE_INFINITY)}),e}function $t(t){const e=t.indexOf("_");if(e<0)return null;const i=t.slice(0,e),r=t.slice(e+1),s=/^(l_[0-9a-z]+)_(.+)$/.exec(r);return s?{entryId:i,listingId:s[1],key:s[2]}:{entryId:i,listingId:null,key:r}}function bt(t,e,i,r){const s=e.get("price");if(!s)return null;const n=t.states[s];if(!n)return null;const o=n.attributes,a={listingId:i,isPrimary:r,retailer:"string"==typeof o.retailer?o.retailer:null,url:"string"==typeof o.product_url?o.product_url:null,price:gt(n.state),currency:"string"==typeof o.unit_of_measurement?o.unit_of_measurement:"string"==typeof o.currency?o.currency:"",inStock:null,discontinued:!0===o.discontinued,stockCount:"number"==typeof o.stock_count?o.stock_count:null,lastCheck:"string"==typeof o.last_check?o.last_check:null,history:mt(o.price_history),imageProxyUrl:null,imageBroken:!1,shipsToUserRegion:"boolean"==typeof o.ships_to_user_region?o.ships_to_user_region:null,entityIds:{price:s}},l=e.get("photo");if(l){const e=t.states[l];if(e)if("unavailable"===e.state||"unknown"===e.state)a.imageBroken=!0;else{const t=e.attributes.entity_picture;"string"==typeof t&&t.length>0&&(a.imageProxyUrl=t)}}const c=e.get("in_stock");if(c){const e=t.states[c];e&&(a.inStock=_t(e.state),a.entityIds.inStock=c)}const d=e.get("discontinued");if(d){const e=t.states[d];if(e){const t=_t(e.state);null!=t&&(a.discontinued=t),a.entityIds.discontinued=d}}return a}function xt(t,e,i,r=2){if(t.length<2)return"";const s=t.length>=4?wt(t):t;if(s.length<2)return"";const n=s.map(t=>t.price),o=Math.min(...n),a=Math.max(...n)-o||1,l=i-2*r,c=e/(s.length-1);let d="";return s.forEach((t,e)=>{const s=e*c,n=i-r-(t.price-o)/a*l;d+=0===e?`M ${s.toFixed(2)} ${n.toFixed(2)}`:` L ${s.toFixed(2)} ${n.toFixed(2)}`}),d}function wt(t,e=5){if(t.length<2)return t;const i=t.map(t=>t.price),r=kt(i),s=i.map(t=>Math.abs(t-r)),n=kt(s);return 0===n?t:t.filter(t=>Math.abs(t.price-r)<=e*n)}function kt(t){const e=[...t].sort((t,e)=>t-e),i=Math.floor(e.length/2);return e.length%2==0?(e[i-1]+e[i])/2:e[i]}let At=class extends at{constructor(){super(...arguments),this.refreshingAlternatives=!1,this.hideNonShipping=!1,this.handleRefresh=t=>{t.stopPropagation(),this.refreshingAlternatives||this.onRefreshAlternatives?.(this.product)}}get headlinePrice(){const{product:t}=this;return null!=t.priceLocal&&t.localCurrency?{value:t.priceLocal,currency:t.localCurrency}:t.discontinued&&null!=t.lastKnownPrice?{value:t.lastKnownPrice,currency:t.lastKnownCurrency??t.currency}:{value:t.price,currency:t.currency||null}}get sourcePriceLine(){const{product:t}=this;return null!=t.priceLocal&&t.localCurrency?t.currency===t.localCurrency?K:ft(t.price,t.currency):K}get priceDelta(){const{product:t}=this;if(null==t.price)return null;const e=t.price;for(let i=t.history.length-1;i>=0;i--){const r=t.history[i].price;if(r!==e)return{amount:Math.abs(e-r),direction:e>r?"up":"down"}}return null}renderDelta(){const t=this.priceDelta;if(null==t)return K;const e="up"===t.direction?"↑":"↓",i="up"===t.direction?"delta delta--up":"delta delta--down";return F`<span class=${i}>${e} ${ft(t.amount,null)}</span>`}renderImage(){const{product:t}=this,e=t.imageProxyUrl??(t.imageBroken?null:t.imageUrl);return e?F`<img
      class="image"
      src=${e}
      alt=${t.title}
      loading="lazy"
    />`:F`<div class="image image--placeholder" role="img" aria-label="No image">
        <ha-icon icon="mdi:tag-search"></ha-icon>
      </div>`}renderSparkline(){const{product:t}=this;if(t.history.length<2)return K;const e=xt(t.history,280,48);return e?F`<svg
      class="sparkline"
      viewBox="0 0 ${280} ${48}"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d=${e} fill="none" stroke="currentColor" stroke-width="1.5" />
    </svg>`:K}renderStatusChips(){const{product:t}=this,e=[];return t.discontinued?e.push(F`<span class="chip chip--warn" title=${t.discontinuedReason??""}>
        Discontinued
      </span>`):!1===t.inStock?e.push(F`<span class="chip chip--warn">Out of stock</span>`):!0===t.inStock&&e.push(F`<span class="chip chip--ok">In stock</span>`),null!=t.stockCount&&t.stockCount>0&&e.push(F`<span class="chip">${t.stockCount} units</span>`),t.retailer&&e.push(F`<span class="chip chip--retailer">${t.retailer}</span>`),e.length?F`<div class="chips">${e}</div>`:K}get cleanedExtremes(){const{product:t}=this;if(t.history.length>=4){const e=wt(t.history);if(e.length>=2){const t=e.map(t=>t.price);return{low:Math.min(...t),high:Math.max(...t)}}}return{low:t.lowest,high:t.highest}}renderAlternatives(){const{product:t}=this,e=null!=t.alternativesError,i=null!=t.alternativesFetchedAt,r=this.hideNonShipping?t.alternatives.filter(t=>!1!==t.shipsToUserRegion):t.alternatives,s=t.alternatives.length-r.length,n=r.length>0;return F`
      <section class="alts">
        <div class="alts__header">
          <span class="alts__title">
            ${n?F`Alternatives <span class="alts__count">${r.length}</span>`:F`Alternatives`}
          </span>
          <span class="alts__meta">
            ${i?yt(t.alternativesFetchedAt):""}
          </span>
          <button
            class="alts__refresh"
            type="button"
            ?disabled=${this.refreshingAlternatives}
            @click=${this.handleRefresh}
            aria-label="Refresh alternatives"
            title="Refresh alternatives"
          >
            <ha-icon
              icon=${this.refreshingAlternatives?"mdi:loading":"mdi:refresh"}
              class=${this.refreshingAlternatives?"alts__refresh-spin":""}
            ></ha-icon>
          </button>
        </div>
        ${e?F`<p class="alts__error">${t.alternativesError}</p>`:K}
        ${n?F`<ul class="alts__list">
              ${r.map(t=>this.renderAlternative(t))}
            </ul>`:e||this.refreshingAlternatives?K:F`<p class="alts__empty">
              ${i?s>0?"All alternatives were hidden (don't ship to your region).":"No alternatives found.":"Click refresh to search for alternatives."}
            </p>`}
        ${n&&s>0?F`<p class="alts__hidden-note">
              ${s} hidden (don't ship to your region)
            </p>`:K}
      </section>
    `}renderAlternative(t){const{product:e}=this;let i=null,r="alts__price";return null!=t.price&&null!=e.price&&t.currency===e.currency&&(i=t.price-e.price,i<0?r="alts__price alts__price--cheaper":i>0&&(r="alts__price alts__price--pricier")),F`
      <li class="alts__row">
        <a
          class="alts__link"
          href=${t.url}
          target="_blank"
          rel="noopener noreferrer"
          @click=${t=>t.stopPropagation()}
          title=${t.notes||t.title}
        >
          <div class="alts__info">
            <span class="alts__row-title">${t.title}</span>
            <span class="alts__row-meta">
              ${t.retailer?F`<span>${t.retailer}</span>`:K}
              ${t.confidence>0?F`<span class="alts__confidence" title="Match confidence">
                    ${Math.round(100*t.confidence)}%
                  </span>`:K}
              ${!0===t.shipsToUserRegion?F`<span class="alts__ships alts__ships--yes" title="Likely ships to your region">
                    ✓ ships
                  </span>`:!1===t.shipsToUserRegion?F`<span class="alts__ships alts__ships--no" title="Likely does not ship to your region">
                    ✗ no ship
                  </span>`:K}
            </span>
          </div>
          <div class=${r}>
            ${null!=t.price?ft(t.price,t.currency):F`<span class="alts__price-unknown">—</span>`}
          </div>
        </a>
      </li>
    `}renderStatRow(){const{product:t}=this,e=[];if(null!=t.targetPrice){const i=null!=t.targetDiff&&t.targetDiff<=0?"stat__value stat__value--good":"stat__value";e.push(F`<div class="stat">
        <span class="stat__label">Target</span>
        <span class=${i}>${ft(t.targetPrice,t.currency)}</span>
      </div>`)}return e.length?F`<div class="stats">${e}</div>`:K}renderListings(){const{product:t}=this;if(0===t.listings.length)return K;const e=this.hideNonShipping?t.listings.filter(t=>t.isPrimary||!1!==t.shipsToUserRegion):t.listings,i=t.listings.length-e.length;return F`
      <section class="listings">
        <div class="listings__header">
          <span class="listings__title">
            Listings <span class="listings__count">${e.length}</span>
          </span>
        </div>
        <ul class="listings__list">
          ${e.map(t=>this.renderListingRow(t))}
        </ul>
        ${i>0?F`<p class="alts__hidden-note">
              ${i} hidden (don't ship to your region)
            </p>`:K}
      </section>
    `}renderListingRow(t){const e=xt(t.history,80,24,2),i=t.discontinued?F`<span class="listings__chip listings__chip--warn">disc.</span>`:!1===t.inStock?F`<span class="listings__chip listings__chip--warn">out</span>`:!0===t.inStock?F`<span class="listings__chip listings__chip--ok">in stock</span>`:K,r=t.imageProxyUrl?F`<img
          class="listings__thumb"
          src=${t.imageProxyUrl}
          alt=""
          loading="lazy"
        />`:F`<span
          class="listings__thumb listings__thumb--placeholder"
          aria-hidden="true"
        ></span>`,s=F`
      ${r}
      <div class="listings__info">
        <span class="listings__row-retailer">
          ${t.retailer??"Unknown"}
          ${t.isPrimary?F`<span class="listings__badge">primary</span>`:K}
        </span>
        <span class="listings__row-meta">
          ${i}
          <span class="listings__last-check">
            ${yt(t.lastCheck)}
          </span>
        </span>
      </div>
      ${e?F`<svg
            class="listings__sparkline"
            viewBox="0 0 ${80} ${24}"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d=${e} fill="none" stroke="currentColor" stroke-width="1.25" />
          </svg>`:F`<span class="listings__sparkline listings__sparkline--empty"></span>`}
      <div class="listings__price">
        ${ft(t.price,t.currency||null)}
      </div>
    `;return F`
      <li class="listings__row">
        ${t.url?F`<a
              class="listings__link"
              href=${t.url}
              target="_blank"
              rel="noopener noreferrer"
              @click=${t=>t.stopPropagation()}
              title=${t.retailer??t.url}
            >
              ${s}
            </a>`:F`<div class="listings__link listings__link--noUrl">${s}</div>`}
        ${t.isPrimary?K:F`<button
              class="listings__remove"
              type="button"
              @click=${e=>this.handleRemoveListing(e,t)}
              aria-label=${`Remove ${t.retailer??"listing"}`}
              title=${`Remove ${t.retailer??"this listing"}`}
            >
              ×
            </button>`}
      </li>
    `}handleRemoveListing(t,e){if(t.stopPropagation(),t.preventDefault(),e.isPrimary)return;const i=e.retailer?`Remove the ${e.retailer} listing from ${this.product.title}?`:`Remove this listing from ${this.product.title}?`;window.confirm(i)&&this.onRemoveListing?.(this.product,e)}handleClick(t){t.target.closest("a")||this.onOpen?.(this.product)}render(){const{product:t}=this,{value:e,currency:i}=this.headlinePrice,r=this.sourcePriceLine;return F`
      <article
        class="card ${t.discontinued?"card--faded":""}"
        @click=${this.handleClick}
        tabindex="0"
        role="button"
        aria-label=${`Open ${t.title}`}
      >
        ${this.renderImage()}
        <div class="body">
          <header class="header">
            <h3 class="title">${t.title}</h3>
            ${this.renderStatusChips()}
          </header>

          <div class="price-block">
            <div class="price">${ft(e,i)}</div>
            ${r===K?this.renderDelta():F`<div class="price-sub">${r} ${this.renderDelta()}</div>`}
          </div>

          ${this.renderSparkline()}
          ${this.renderStatRow()}
          ${this.renderListings()}
          ${this.renderAlternatives()}

          ${t.discontinued&&t.discontinuedReason?F`<p class="discontinued-reason">${t.discontinuedReason}</p>`:K}

          <footer class="footer">
            <span class="last-check">
              Last check: ${yt(t.lastCheck)}
            </span>
            ${t.url?F`<a class="link" href=${t.url} target="_blank" rel="noopener">
                  Open at retailer ↗
                </a>`:K}
          </footer>
        </div>
      </article>
    `}};var St;At.styles=o`
    :host {
      display: block;
    }

    .card {
      display: flex;
      flex-direction: column;
      background: var(--card-background-color, #fff);
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.08));
      overflow: hidden;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease;
      color: var(--primary-text-color, #212121);
    }
    .card:hover,
    .card:focus-visible {
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
      outline: none;
    }
    .card--faded {
      opacity: 0.65;
    }
    .card--faded:hover {
      opacity: 0.85;
    }

    .image {
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: contain;
      background: var(--secondary-background-color, #f5f5f5);
      display: block;
    }
    .image--placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--secondary-text-color, #757575);
      --mdc-icon-size: 48px;
    }

    .body {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      flex: 1;
    }

    .header {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .title {
      margin: 0;
      font-size: 1rem;
      font-weight: 500;
      line-height: 1.3;
      /* Clamp very long titles (Amazon-style "CORSAIR Dominator Titanium ..."
         that go on for 100 chars) so card heights stay consistent. */
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--secondary-background-color, #f0f0f0);
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
    }
    .chip--ok {
      background: var(--success-color, #43a047);
      color: #fff;
    }
    .chip--warn {
      background: var(--warning-color, #ffa726);
      color: #fff;
    }
    .chip--retailer {
      background: transparent;
      border: 1px solid var(--divider-color, #e0e0e0);
      color: var(--secondary-text-color, #757575);
    }

    .price-block {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }
    .price {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--primary-text-color, #212121);
    }
    .price-sub {
      font-size: 0.875rem;
      color: var(--secondary-text-color, #757575);
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
    }

    /* Price-movement indicator: red ↑ for an increase, green ↓ for
       a drop. Sits inline next to whichever line displays the
       source-currency price. Compact font so it doesn't compete
       with the headline. */
    .delta {
      font-size: 0.85rem;
      font-weight: 600;
      white-space: nowrap;
      padding: 1px 6px;
      border-radius: 4px;
    }
    .delta--up {
      color: var(--error-color, #d32f2f);
      background: var(--error-color-faded, rgba(211, 47, 47, 0.1));
    }
    .delta--down {
      color: var(--success-color, #43a047);
      background: var(--success-color-faded, rgba(67, 160, 71, 0.1));
    }

    .sparkline {
      width: 100%;
      height: 48px;
      color: var(--primary-color, #03a9f4);
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
      gap: 8px;
    }
    .stat {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .stat__label {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--secondary-text-color, #757575);
    }
    .stat__value {
      font-size: 0.875rem;
      font-weight: 500;
    }
    .stat__value--good {
      color: var(--success-color, #43a047);
    }

    .discontinued-reason {
      margin: 0;
      font-size: 0.8rem;
      font-style: italic;
      color: var(--warning-color, #ffa726);
    }

    .footer {
      margin-top: auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
    }
    .link {
      color: var(--primary-color, #03a9f4);
      text-decoration: none;
    }
    .link:hover {
      text-decoration: underline;
    }

    /* --- Alternatives section --- */
    .alts {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--divider-color, #e0e0e0);
    }
    .alts__header {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .alts__title {
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--primary-text-color, #212121);
      flex: 0 0 auto;
    }
    .alts__count {
      display: inline-block;
      min-width: 18px;
      padding: 0 6px;
      font-size: 0.7rem;
      font-weight: 600;
      text-align: center;
      border-radius: 999px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      margin-left: 4px;
    }
    .alts__meta {
      flex: 1 1 auto;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
    }
    .alts__refresh {
      flex: 0 0 auto;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 4px;
      cursor: pointer;
      color: var(--secondary-text-color, #757575);
      --mdc-icon-size: 18px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .alts__refresh:hover:not(:disabled) {
      color: var(--primary-color, #03a9f4);
      background: var(--secondary-background-color, #f5f5f5);
      border-color: var(--divider-color, #e0e0e0);
    }
    .alts__refresh:disabled {
      cursor: wait;
      opacity: 0.6;
    }
    @keyframes alts-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .alts__refresh-spin {
      animation: alts-spin 1.2s linear infinite;
    }
    .alts__list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .alts__row {
      margin: 0;
      padding: 0;
    }
    .alts__link {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 6px 8px;
      border-radius: 6px;
      text-decoration: none;
      color: inherit;
      transition: background 120ms ease;
    }
    .alts__link:hover {
      background: var(--secondary-background-color, #f5f5f5);
    }
    .alts__info {
      flex: 1 1 auto;
      min-width: 0;  /* allow truncation in flex children */
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .alts__row-title {
      font-size: 0.8rem;
      line-height: 1.3;
      color: var(--primary-text-color, #212121);
      /* Single-line clamp; rely on title attr for the full text. */
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .alts__row-meta {
      display: flex;
      gap: 8px;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
    }
    .alts__confidence {
      font-variant-numeric: tabular-nums;
    }
    .alts__ships {
      font-size: 0.7rem;
      padding: 1px 6px;
      border-radius: 999px;
      font-weight: 600;
      white-space: nowrap;
    }
    .alts__ships--yes {
      background: rgba(46, 125, 50, 0.15);
      color: var(--success-color, #2e7d32);
    }
    .alts__ships--no {
      background: rgba(120, 120, 120, 0.18);
      color: var(--secondary-text-color, #757575);
      text-decoration: line-through;
    }
    .alts__price {
      flex: 0 0 auto;
      font-size: 0.85rem;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
    }
    .alts__price--cheaper {
      color: var(--success-color, #43a047);
    }
    .alts__price--pricier {
      color: var(--warning-color, #ffa726);
    }
    .alts__price-unknown {
      color: var(--secondary-text-color, #757575);
      font-weight: 400;
    }
    .alts__empty {
      margin: 4px 0 0;
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      font-style: italic;
    }
    .alts__hidden-note {
      margin: 2px 0 0;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
      font-style: italic;
    }
    .alts__error {
      margin: 0;
      font-size: 0.75rem;
      color: var(--error-color, #c62828);
      padding: 6px 8px;
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 6px;
    }

    /* --- Listings section ---
       Renders all user-tracked listings of this product as rows.
       Visually echoes the alts section so the two read as siblings
       (both are "other URLs" surfaced beneath the headline), but
       uses dashed top border + neutral count badge to distinguish
       "explicitly tracked" listings from "discovered" alternatives. */
    .listings {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding-top: 8px;
      border-top: 1px dashed var(--divider-color, #e0e0e0);
    }
    .listings__header {
      display: flex;
      align-items: center;
    }
    .listings__title {
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--primary-text-color, #212121);
    }
    .listings__count {
      display: inline-block;
      min-width: 18px;
      padding: 0 6px;
      font-size: 0.7rem;
      font-weight: 600;
      text-align: center;
      border-radius: 999px;
      background: var(--secondary-background-color, #e0e0e0);
      color: var(--secondary-text-color, #757575);
      margin-left: 4px;
    }
    .listings__list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .listings__row {
      display: flex;
      align-items: center;
      gap: 4px;
      margin: 0;
      padding: 0;
    }
    .listings__link {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 8px;
      border-radius: 6px;
      text-decoration: none;
      color: inherit;
      transition: background 120ms ease;
    }
    .listings__link:hover {
      background: var(--secondary-background-color, #f5f5f5);
    }
    .listings__link--noUrl {
      cursor: default;
    }
    .listings__link--noUrl:hover {
      background: transparent;
    }
    .listings__thumb {
      flex: 0 0 auto;
      width: 32px;
      height: 32px;
      border-radius: 5px;
      object-fit: cover;
      background: var(--secondary-background-color, #f0f0f0);
    }
    .listings__thumb--placeholder {
      display: inline-block;
      border: 1px solid var(--divider-color, #e0e0e0);
      box-sizing: border-box;
    }
    .listings__info {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .listings__row-retailer {
      font-size: 0.8rem;
      line-height: 1.3;
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .listings__badge {
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 1px 6px;
      border-radius: 999px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
    }
    .listings__row-meta {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
    }
    .listings__chip {
      font-size: 0.65rem;
      padding: 1px 6px;
      border-radius: 999px;
      font-weight: 600;
      white-space: nowrap;
      background: var(--secondary-background-color, #f0f0f0);
      color: var(--secondary-text-color, #757575);
    }
    .listings__chip--ok {
      background: rgba(46, 125, 50, 0.15);
      color: var(--success-color, #2e7d32);
    }
    .listings__chip--warn {
      background: rgba(211, 47, 47, 0.12);
      color: var(--error-color, #c62828);
    }
    .listings__last-check {
      white-space: nowrap;
    }
    .listings__sparkline {
      flex: 0 0 80px;
      width: 80px;
      height: 24px;
      color: var(--primary-color, #03a9f4);
    }
    .listings__sparkline--empty {
      /* Placeholder takes the same space when history < 2 points
         so the columns line up across rows. */
      display: inline-block;
    }
    .listings__price {
      flex: 0 0 auto;
      font-size: 0.85rem;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
    }
    .listings__remove {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .listings__remove:hover {
      color: var(--error-color, #c62828);
      background: rgba(211, 47, 47, 0.08);
      border-color: rgba(211, 47, 47, 0.2);
    }
    .listings__remove:focus-visible {
      outline: 2px solid var(--error-color, #c62828);
      outline-offset: 1px;
    }
  `,t([ht({attribute:!1})],At.prototype,"product",void 0),t([ht({attribute:!1})],At.prototype,"onOpen",void 0),t([ht({attribute:!1})],At.prototype,"onRefreshAlternatives",void 0),t([ht({type:Boolean,attribute:!1})],At.prototype,"refreshingAlternatives",void 0),t([ht({type:Boolean,attribute:!1})],At.prototype,"hideNonShipping",void 0),t([ht({attribute:!1})],At.prototype,"onRemoveListing",void 0),At=t([ct("price-watch-card")],At);let PriceWatchPanel=St=class extends at{constructor(){super(),this._products=[],this._registry=null,this._registryError=null,this._connected=!1,this._refreshingEntries=new Set,this._hideNonShipping=!1,this._conn=null,this._states={},this._handleOpen=t=>{t.url&&window.open(t.url,"_blank","noopener,noreferrer")},this._handleRefreshAlternatives=async t=>{if(this._conn&&!this._refreshingEntries.has(t.entryId)){this._refreshingEntries=new Set([...this._refreshingEntries,t.entryId]);try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"find_alternatives",service_data:{entry_id:t.entryId}})}catch(t){console.error("[price-watch-panel] find_alternatives failed:",t)}finally{const e=new Set(this._refreshingEntries);e.delete(t.entryId),this._refreshingEntries=e}}},this._handleRemoveListing=async(t,e)=>{if(this._conn)if(e.isPrimary)console.warn("[price-watch-panel] refusing to remove primary listing",e.listingId);else try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"remove_listing",service_data:{entry_id:t.entryId,listing_id:e.listingId}})}catch(t){console.error("[price-watch-panel] remove_listing failed:",t)}},this._handleToggleHideNonShipping=()=>{this._hideNonShipping=!this._hideNonShipping;try{localStorage.setItem(St.HIDE_NONSHIP_KEY,this._hideNonShipping?"1":"0")}catch{}},this._handleAddProduct=()=>{window.history.pushState(null,"","/config/integrations/dashboard/add?domain=price_watch"),window.dispatchEvent(new CustomEvent("location-changed"))};try{this._hideNonShipping="1"===localStorage.getItem(St.HIDE_NONSHIP_KEY)}catch{}}connectedCallback(){super.connectedCallback(),this._bootstrap()}disconnectedCallback(){super.disconnectedCallback(),this._unsubState?.(),this._unsubRegistry?.(),this._unsubState=void 0,this._unsubRegistry=void 0}async _bootstrap(){const t=window.hassConnection;if(!t)return void(this._registryError="Home Assistant WebSocket connection not available on this page. Try reloading.");let e;try{const i=await t;e=i.conn,this._conn=e,this._connected=!0}catch(t){const e=t instanceof Error?t.message:String(t);return void(this._registryError=`Could not open HA connection: ${e}`)}try{await this._fetchRegistry(e),await this._fetchInitialStates(e),this._unsubState=await e.subscribeEvents(t=>this._onStateChanged(t),"state_changed"),this._unsubRegistry=await e.subscribeEvents(()=>{this._fetchRegistry(e).then(()=>this._fetchInitialStates(e))},"entity_registry_updated")}catch(t){const e=t instanceof Error?t.message:String(t);this._registryError=`Setup failed after connection: ${e}`,console.error("[price-watch-panel]",t)}}async _fetchRegistry(t){const e=await t.sendMessagePromise({type:"config/entity_registry/list"}),i=new Map;for(const t of e)"price_watch"===t.platform&&i.set(t.unique_id,t.entity_id);this._registry={byUniqueId:i},this._registryError=null,this._rebuildProducts()}async _fetchInitialStates(t){if(!this._registry)return;const e=new Set(this._registry.byUniqueId.values()),i=await t.sendMessagePromise({type:"get_states"}),r={};for(const t of i)e.has(t.entity_id)&&(r[t.entity_id]=t);this._states=r,this._rebuildProducts()}_onStateChanged(t){const{entity_id:e,new_state:i}=t.data;if(!this._registry)return;new Set(this._registry.byUniqueId.values()).has(e)&&(null===i?delete this._states[e]:this._states={...this._states,[e]:i},this._rebuildProducts())}_rebuildProducts(){if(!this._registry)return void(this._products=[]);const t={states:this._states};this._products=function(t,e){const i=new Map;for(const[t,r]of e.byUniqueId){const e=$t(t);if(!e)continue;let s=i.get(e.entryId);if(s||(s={legacy:new Map,listings:new Map},i.set(e.entryId,s)),null===e.listingId)s.legacy.set(e.key,r);else{let t=s.listings.get(e.listingId);t||(t=new Map,s.listings.set(e.listingId,t)),t.set(e.key,r)}}const r=[];for(const[e,s]of i){const i=s.legacy,n=i.get("price");if(!n)continue;const o=t.states[n];if(!o)continue;const a=o.attributes,l={entryId:e,title:String(a.title??a.friendly_name??"Unknown product"),url:String(a.product_url??""),retailer:"string"==typeof a.retailer?a.retailer:null,imageUrl:"string"==typeof a.image_url?a.image_url:null,imageProxyUrl:null,imageBroken:!1,price:gt(o.state),currency:"string"==typeof a.unit_of_measurement?a.unit_of_measurement:"string"==typeof a.currency?a.currency:"",priceLocal:null,localCurrency:null,lowest:null,highest:null,targetDiff:null,targetPrice:"number"==typeof a.target_price?a.target_price:null,inStock:null,stockCount:"number"==typeof a.stock_count?a.stock_count:null,discontinued:!0===a.discontinued,discontinuedReason:"string"==typeof a.discontinued_reason?a.discontinued_reason:null,discontinuedAt:"string"==typeof a.discontinued_at?a.discontinued_at:null,lastKnownPrice:"number"==typeof a.last_known_price?a.last_known_price:null,lastKnownCurrency:"string"==typeof a.last_known_currency?a.last_known_currency:null,lastCheck:"string"==typeof a.last_check?a.last_check:null,history:mt(a.price_history),alternatives:vt(a.alternatives),alternativesFetchedAt:"string"==typeof a.alternatives_fetched_at?a.alternatives_fetched_at:null,alternativesError:"string"==typeof a.alternatives_error&&a.alternatives_error?a.alternatives_error:null,entityIds:{price:n},listings:[]},c=[["price_local",t=>{l.priceLocal=gt(t.state),l.localCurrency="string"==typeof t.attributes.unit_of_measurement?t.attributes.unit_of_measurement:null,l.entityIds.priceLocal=t.entity_id}],["lowest",t=>{l.lowest=gt(t.state),l.entityIds.lowest=t.entity_id}],["highest",t=>{l.highest=gt(t.state),l.entityIds.highest=t.entity_id}],["target_diff",t=>{l.targetDiff=gt(t.state),l.entityIds.targetDiff=t.entity_id}],["stock_count",t=>{l.stockCount=gt(t.state),l.entityIds.stockCount=t.entity_id}],["in_stock",t=>{l.inStock=_t(t.state),l.entityIds.inStock=t.entity_id}],["discontinued",t=>{const e=_t(t.state);null!=e&&(l.discontinued=e),l.entityIds.discontinued=t.entity_id}],["photo",t=>{if("unavailable"===t.state||"unknown"===t.state)return void(l.imageBroken=!0);const e=t.attributes.entity_picture;"string"==typeof e&&e.length>0&&(l.imageProxyUrl=e)}]];for(const[e,r]of c){const s=i.get(e);if(!s)continue;const n=t.states[s];n&&r(n)}const d="string"==typeof a.listing_id&&a.listing_id?a.listing_id:`l_${e.slice(-12).toLowerCase()}`,p=bt(t,s.legacy,d,!0);p&&l.listings.push(p);for(const[e,i]of s.listings){const r=bt(t,i,e,!1);r&&l.listings.push(r)}r.push(l)}return r.sort((t,e)=>t.discontinued!==e.discontinued?t.discontinued?1:-1:t.title.localeCompare(e.title)),r}(t,this._registry)}_renderHeader(){const t=this._products.length,e=this._products.filter(t=>t.discontinued).length;return F`
      <header class="panel-header">
        <div class="panel-header__title">
          <h1>Price Watch</h1>
          <div class="panel-header__counts">
            ${t-e} active${e>0?F` · ${e} discontinued`:K}
          </div>
        </div>
        <div class="panel-header__actions">
          <label
            class="ship-toggle"
            title="Hide alternatives that don't ship to your region"
          >
            <input
              type="checkbox"
              .checked=${this._hideNonShipping}
              @change=${this._handleToggleHideNonShipping}
            />
            <span>Ships to me only</span>
          </label>
          <button class="add-button" @click=${this._handleAddProduct}>
            + Add product
          </button>
        </div>
      </header>
    `}_renderEmptyState(){return F`
      <div class="empty">
        <div class="empty__icon">🏷️</div>
        <h2>No products tracked yet</h2>
        <p>Add a product to start watching its price.</p>
        <button class="add-button" @click=${this._handleAddProduct}>
          + Add product
        </button>
      </div>
    `}_renderError(){return F`
      <div class="error">
        <div class="error__icon">⚠</div>
        <p>${this._registryError}</p>
      </div>
    `}_renderLoading(){return F`
      <div class="loading">
        <p>Loading tracked products…</p>
      </div>
    `}_renderGrid(){return F`
      <div class="grid">
        ${this._products.map(t=>F`
            <price-watch-card
              .product=${t}
              .onOpen=${this._handleOpen}
              .onRefreshAlternatives=${this._handleRefreshAlternatives}
              .refreshingAlternatives=${this._refreshingEntries.has(t.entryId)}
              .hideNonShipping=${this._hideNonShipping}
              .onRemoveListing=${this._handleRemoveListing}
            ></price-watch-card>
          `)}
      </div>
    `}render(){return F`
      <div class="panel">
        ${this._renderHeader()}
        ${this._registryError?this._renderError():this._connected&&this._registry?0===this._products.length?this._renderEmptyState():this._renderGrid():this._renderLoading()}
      </div>
    `}};PriceWatchPanel.HIDE_NONSHIP_KEY="price-watch:hide-non-shipping",PriceWatchPanel.styles=o`
    :host {
      display: block;
      width: 100%;
      min-height: 100vh;
      background: var(--primary-background-color, #fafafa);
      color: var(--primary-text-color, #212121);
      box-sizing: border-box;
    }

    .panel {
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
      box-sizing: border-box;
    }

    .panel-header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }
    .panel-header h1 {
      margin: 0;
      font-size: 1.75rem;
      font-weight: 500;
    }
    .panel-header__counts {
      color: var(--secondary-text-color, #757575);
      font-size: 0.875rem;
      margin-top: 4px;
    }

    .panel-header__actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .ship-toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }
    .ship-toggle input {
      cursor: pointer;
      accent-color: var(--primary-color, #03a9f4);
      margin: 0;
    }

    .add-button {
      padding: 8px 16px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      border: none;
      border-radius: 999px;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: filter 120ms ease;
    }
    .add-button:hover {
      filter: brightness(1.1);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }

    .empty,
    .error,
    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      padding: 48px 16px;
      text-align: center;
      color: var(--secondary-text-color, #757575);
    }
    .empty__icon {
      font-size: 64px;
    }
    .error__icon {
      font-size: 48px;
      color: var(--error-color, #f44336);
    }
    .empty h2 {
      margin: 0;
      font-size: 1.25rem;
      color: var(--primary-text-color, #212121);
    }
    .empty p,
    .error p,
    .loading p {
      margin: 0;
    }
  `,t([ut()],PriceWatchPanel.prototype,"_products",void 0),t([ut()],PriceWatchPanel.prototype,"_registry",void 0),t([ut()],PriceWatchPanel.prototype,"_registryError",void 0),t([ut()],PriceWatchPanel.prototype,"_connected",void 0),t([ut()],PriceWatchPanel.prototype,"_refreshingEntries",void 0),t([ut()],PriceWatchPanel.prototype,"_hideNonShipping",void 0),PriceWatchPanel=St=t([ct("price-watch-panel")],PriceWatchPanel);export{PriceWatchPanel};
