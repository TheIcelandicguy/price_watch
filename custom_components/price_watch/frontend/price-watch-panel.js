function t(t,e,r,i){var s,n=arguments.length,o=n<3?e:null===i?i=Object.getOwnPropertyDescriptor(e,r):i;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(t,e,r,i);else for(var a=t.length-1;a>=0;a--)(s=t[a])&&(o=(n<3?s(o):n>3?s(e,r,o):s(e,r))||o);return n>3&&o&&Object.defineProperty(e,r,o),o}"function"==typeof SuppressedError&&SuppressedError;const e=globalThis,r=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,i=Symbol(),s=new WeakMap;let n=class{constructor(t,e,r){if(this._$cssResult$=!0,r!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(r&&void 0===t){const r=void 0!==e&&1===e.length;r&&(t=s.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),r&&s.set(e,t))}return t}toString(){return this.cssText}};const o=(t,...e)=>{const r=1===t.length?t[0]:e.reduce((e,r,i)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+t[i+1],t[0]);return new n(r,t,i)},a=r?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const r of t.cssRules)e+=r.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,i))(e)})(t):t,{is:l,defineProperty:c,getOwnPropertyDescriptor:d,getOwnPropertyNames:p,getOwnPropertySymbols:h,getPrototypeOf:u}=Object,g=globalThis,_=g.trustedTypes,f=_?_.emptyScript:"",y=g.reactiveElementPolyfillSupport,m=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?f:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=null!==t;break;case Number:r=null===t?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch(t){r=null}}return r}},b=(t,e)=>!l(t,e),$={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:b};Symbol.metadata??=Symbol("metadata"),g.litPropertyMetadata??=new WeakMap;let x=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=$){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const r=Symbol(),i=this.getPropertyDescriptor(t,r,e);void 0!==i&&c(this.prototype,t,i)}}static getPropertyDescriptor(t,e,r){const{get:i,set:s}=d(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:i,set(e){const n=i?.call(this);s?.call(this,e),this.requestUpdate(t,n,r)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??$}static _$Ei(){if(this.hasOwnProperty(m("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(m("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m("properties"))){const t=this.properties,e=[...p(t),...h(t)];for(const r of e)this.createProperty(r,t[r])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,r]of e)this.elementProperties.set(t,r)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const r=this._$Eu(t,e);void 0!==r&&this._$Eh.set(r,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const r=new Set(t.flat(1/0).reverse());for(const t of r)e.unshift(a(t))}else void 0!==t&&e.push(a(t));return e}static _$Eu(t,e){const r=e.attribute;return!1===r?void 0:"string"==typeof r?r:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const r of e.keys())this.hasOwnProperty(r)&&(t.set(r,this[r]),delete this[r]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((t,i)=>{if(r)t.adoptedStyleSheets=i.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const r of i){const i=document.createElement("style"),s=e.litNonce;void 0!==s&&i.setAttribute("nonce",s),i.textContent=r.cssText,t.appendChild(i)}})(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,r){this._$AK(t,r)}_$ET(t,e){const r=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,r);if(void 0!==i&&!0===r.reflect){const s=(void 0!==r.converter?.toAttribute?r.converter:v).toAttribute(e,r.type);this._$Em=t,null==s?this.removeAttribute(i):this.setAttribute(i,s),this._$Em=null}}_$AK(t,e){const r=this.constructor,i=r._$Eh.get(t);if(void 0!==i&&this._$Em!==i){const t=r.getPropertyOptions(i),s="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=i;const n=s.fromAttribute(e,t.type);this[i]=n??this._$Ej?.get(i)??n,this._$Em=null}}requestUpdate(t,e,r,i=!1,s){if(void 0!==t){const n=this.constructor;if(!1===i&&(s=this[t]),r??=n.getPropertyOptions(t),!((r.hasChanged??b)(s,e)||r.useDefault&&r.reflect&&s===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,r))))return;this.C(t,e,r)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:r,reflect:i,wrapped:s},n){r&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),!0!==s||void 0!==n)||(this._$AL.has(t)||(this.hasUpdated||r||(e=void 0),this._$AL.set(t,e)),!0===i&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,r]of t){const{wrapped:t}=r,i=this[e];!0!==t||this._$AL.has(e)||void 0===i||this.C(e,void 0,r,i)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};x.elementStyles=[],x.shadowRootOptions={mode:"open"},x[m("elementProperties")]=new Map,x[m("finalized")]=new Map,y?.({ReactiveElement:x}),(g.reactiveElementVersions??=[]).push("2.1.2");const w=globalThis,k=t=>t,A=w.trustedTypes,S=A?A.createPolicy("lit-html",{createHTML:t=>t}):void 0,E="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,C="?"+P,R=`<${C}>`,U=document,I=()=>U.createComment(""),M=t=>null===t||"object"!=typeof t&&"function"!=typeof t,z=Array.isArray,O="[ \t\n\f\r]",L=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,N=/-->/g,T=/>/g,H=RegExp(`>|${O}(?:([^\\s"'>=/]+)(${O}*=${O}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),D=/'/g,j=/"/g,B=/^(?:script|style|textarea|title)$/i,F=(t=>(e,...r)=>({_$litType$:t,strings:e,values:r}))(1),q=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),W=new WeakMap,K=U.createTreeWalker(U,129);function Y(t,e){if(!z(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==S?S.createHTML(e):e}const G=(t,e)=>{const r=t.length-1,i=[];let s,n=2===e?"<svg>":3===e?"<math>":"",o=L;for(let e=0;e<r;e++){const r=t[e];let a,l,c=-1,d=0;for(;d<r.length&&(o.lastIndex=d,l=o.exec(r),null!==l);)d=o.lastIndex,o===L?"!--"===l[1]?o=N:void 0!==l[1]?o=T:void 0!==l[2]?(B.test(l[2])&&(s=RegExp("</"+l[2],"g")),o=H):void 0!==l[3]&&(o=H):o===H?">"===l[0]?(o=s??L,c=-1):void 0===l[1]?c=-2:(c=o.lastIndex-l[2].length,a=l[1],o=void 0===l[3]?H:'"'===l[3]?j:D):o===j||o===D?o=H:o===N||o===T?o=L:(o=H,s=void 0);const p=o===H&&t[e+1].startsWith("/>")?" ":"";n+=o===L?r+R:c>=0?(i.push(a),r.slice(0,c)+E+r.slice(c)+P+p):r+P+(-2===c?e:p)}return[Y(t,n+(t[r]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),i]};class J{constructor({strings:t,_$litType$:e},r){let i;this.parts=[];let s=0,n=0;const o=t.length-1,a=this.parts,[l,c]=G(t,e);if(this.el=J.createElement(l,r),K.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(i=K.nextNode())&&a.length<o;){if(1===i.nodeType){if(i.hasAttributes())for(const t of i.getAttributeNames())if(t.endsWith(E)){const e=c[n++],r=i.getAttribute(t).split(P),o=/([.?@])?(.*)/.exec(e);a.push({type:1,index:s,name:o[2],strings:r,ctor:"."===o[1]?et:"?"===o[1]?rt:"@"===o[1]?it:tt}),i.removeAttribute(t)}else t.startsWith(P)&&(a.push({type:6,index:s}),i.removeAttribute(t));if(B.test(i.tagName)){const t=i.textContent.split(P),e=t.length-1;if(e>0){i.textContent=A?A.emptyScript:"";for(let r=0;r<e;r++)i.append(t[r],I()),K.nextNode(),a.push({type:2,index:++s});i.append(t[e],I())}}}else if(8===i.nodeType)if(i.data===C)a.push({type:2,index:s});else{let t=-1;for(;-1!==(t=i.data.indexOf(P,t+1));)a.push({type:7,index:s}),t+=P.length-1}s++}}static createElement(t,e){const r=U.createElement("template");return r.innerHTML=t,r}}function Z(t,e,r=t,i){if(e===q)return e;let s=void 0!==i?r._$Co?.[i]:r._$Cl;const n=M(e)?void 0:e._$litDirective$;return s?.constructor!==n&&(s?._$AO?.(!1),void 0===n?s=void 0:(s=new n(t),s._$AT(t,r,i)),void 0!==i?(r._$Co??=[])[i]=s:r._$Cl=s),void 0!==s&&(e=Z(t,s._$AS(t,e.values),s,i)),e}class Q{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:r}=this._$AD,i=(t?.creationScope??U).importNode(e,!0);K.currentNode=i;let s=K.nextNode(),n=0,o=0,a=r[0];for(;void 0!==a;){if(n===a.index){let e;2===a.type?e=new X(s,s.nextSibling,this,t):1===a.type?e=new a.ctor(s,a.name,a.strings,this,t):6===a.type&&(e=new st(s,this,t)),this._$AV.push(e),a=r[++o]}n!==a?.index&&(s=K.nextNode(),n++)}return K.currentNode=U,i}p(t){let e=0;for(const r of this._$AV)void 0!==r&&(void 0!==r.strings?(r._$AI(t,r,e),e+=r.strings.length-2):r._$AI(t[e])),e++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,r,i){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=r,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Z(this,t,e),M(t)?t===V||null==t||""===t?(this._$AH!==V&&this._$AR(),this._$AH=V):t!==this._$AH&&t!==q&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>z(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==V&&M(this._$AH)?this._$AA.nextSibling.data=t:this.T(U.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:r}=t,i="number"==typeof r?this._$AC(t):(void 0===r.el&&(r.el=J.createElement(Y(r.h,r.h[0]),this.options)),r);if(this._$AH?._$AD===i)this._$AH.p(e);else{const t=new Q(i,this),r=t.u(this.options);t.p(e),this.T(r),this._$AH=t}}_$AC(t){let e=W.get(t.strings);return void 0===e&&W.set(t.strings,e=new J(t)),e}k(t){z(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let r,i=0;for(const s of t)i===e.length?e.push(r=new X(this.O(I()),this.O(I()),this,this.options)):r=e[i],r._$AI(s),i++;i<e.length&&(this._$AR(r&&r._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=k(t).nextSibling;k(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class tt{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,r,i,s){this.type=1,this._$AH=V,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=s,r.length>2||""!==r[0]||""!==r[1]?(this._$AH=Array(r.length-1).fill(new String),this.strings=r):this._$AH=V}_$AI(t,e=this,r,i){const s=this.strings;let n=!1;if(void 0===s)t=Z(this,t,e,0),n=!M(t)||t!==this._$AH&&t!==q,n&&(this._$AH=t);else{const i=t;let o,a;for(t=s[0],o=0;o<s.length-1;o++)a=Z(this,i[r+o],e,o),a===q&&(a=this._$AH[o]),n||=!M(a)||a!==this._$AH[o],a===V?t=V:t!==V&&(t+=(a??"")+s[o+1]),this._$AH[o]=a}n&&!i&&this.j(t)}j(t){t===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class et extends tt{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===V?void 0:t}}class rt extends tt{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==V)}}class it extends tt{constructor(t,e,r,i,s){super(t,e,r,i,s),this.type=5}_$AI(t,e=this){if((t=Z(this,t,e,0)??V)===q)return;const r=this._$AH,i=t===V&&r!==V||t.capture!==r.capture||t.once!==r.once||t.passive!==r.passive,s=t!==V&&(r===V||i);i&&this.element.removeEventListener(this.name,this,r),s&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class st{constructor(t,e,r){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=r}get _$AU(){return this._$AM._$AU}_$AI(t){Z(this,t)}}const nt=w.litHtmlPolyfillSupport;nt?.(J,X),(w.litHtmlVersions??=[]).push("3.3.3");const ot=globalThis;class at extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,r)=>{const i=r?.renderBefore??e;let s=i._$litPart$;if(void 0===s){const t=r?.renderBefore??null;i._$litPart$=s=new X(e.insertBefore(I(),t),t,void 0,r??{})}return s._$AI(t),s})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return q}}at._$litElement$=!0,at.finalized=!0,ot.litElementHydrateSupport?.({LitElement:at});const lt=ot.litElementPolyfillSupport;lt?.({LitElement:at}),(ot.litElementVersions??=[]).push("4.2.2");const ct=t=>(e,r)=>{void 0!==r?r.addInitializer(()=>{customElements.define(t,e)}):customElements.define(t,e)},dt={attribute:!0,type:String,converter:v,reflect:!1,hasChanged:b},pt=(t=dt,e,r)=>{const{kind:i,metadata:s}=r;let n=globalThis.litPropertyMetadata.get(s);if(void 0===n&&globalThis.litPropertyMetadata.set(s,n=new Map),"setter"===i&&((t=Object.create(t)).wrapped=!0),n.set(r.name,t),"accessor"===i){const{name:i}=r;return{set(r){const s=e.get.call(this);e.set.call(this,r),this.requestUpdate(i,s,t,!0,r)},init(e){return void 0!==e&&this.C(i,void 0,t,e),e}}}if("setter"===i){const{name:i}=r;return function(r){const s=this[i];e.call(this,r),this.requestUpdate(i,s,t,!0,r)}}throw Error("Unsupported decorator location: "+i)};function ht(t){return(e,r)=>"object"==typeof r?pt(t,e,r):((t,e,r)=>{const i=e.hasOwnProperty(r);return e.constructor.createProperty(r,t),i?Object.getOwnPropertyDescriptor(e,r):void 0})(t,e,r)}function ut(t){return ht({...t,state:!0,attribute:!1})}function gt(t){if(null==t||"unknown"===t||"unavailable"===t)return null;const e=Number(t);return Number.isFinite(e)?e:null}function _t(t){return null==t||"unknown"===t||"unavailable"===t?null:"on"===t||"true"===t||"off"!==t&&"false"!==t&&null}function ft(t,e,r="en"){if(null==t)return"—";if(!e)return t.toLocaleString(r);try{return new Intl.NumberFormat(r,{style:"currency",currency:e,maximumFractionDigits:2}).format(t)}catch{return`${t.toLocaleString(r,{maximumFractionDigits:2})} ${e}`}}function yt(t,e="en"){if(!t)return"never";const r=new Date(t).getTime();if(Number.isNaN(r))return t;const i=Date.now()-r,s=Math.round(i/1e3),n=Math.abs(s),o=new Intl.RelativeTimeFormat(e,{numeric:"auto"});return n<60?o.format(-s,"second"):n<3600?o.format(-Math.round(s/60),"minute"):n<86400?o.format(-Math.round(s/3600),"hour"):n<2592e3?o.format(-Math.round(s/86400),"day"):o.format(-Math.round(s/2592e3),"month")}function mt(t){if(!Array.isArray(t))return[];const e=[];for(const r of t)if(null!=r&&"object"==typeof r&&"price"in r&&"ts"in r){const t=r,i="number"==typeof t.price?t.price:null;if(null==i)continue;e.push({ts:String(t.ts??""),price:i,currency:String(t.currency??""),in_stock:!1!==t.in_stock})}return e}function vt(t){if(!Array.isArray(t))return[];const e=[];for(const r of t){if(!r||"object"!=typeof r)continue;const t=r,i="string"==typeof t.title?t.title:"",s="string"==typeof t.url?t.url:"";i&&s&&e.push({title:i,url:s,price:"number"==typeof t.price?t.price:null,currency:"string"==typeof t.currency?t.currency:"",retailer:"string"==typeof t.retailer?t.retailer:"",imageUrl:"string"==typeof t.image_url&&t.image_url?t.image_url:null,confidence:"number"==typeof t.confidence?Math.max(0,Math.min(1,t.confidence)):0,notes:"string"==typeof t.notes?t.notes:"",shipsToUserRegion:"boolean"==typeof t.ships_to_user_region?t.ships_to_user_region:null})}return e.sort((t,e)=>{if(e.confidence!==t.confidence)return e.confidence-t.confidence;return(t.price??Number.POSITIVE_INFINITY)-(e.price??Number.POSITIVE_INFINITY)}),e}function bt(t){const e=t.indexOf("_");if(e<0)return null;const r=t.slice(0,e),i=t.slice(e+1),s=/^(l_[0-9a-z]+)_(.+)$/.exec(i);return s?{entryId:r,listingId:s[1],key:s[2]}:{entryId:r,listingId:null,key:i}}function $t(t,e,r,i){const s=e.get("price");if(!s)return null;const n=t.states[s];if(!n)return null;const o=n.attributes,a={listingId:r,isPrimary:i,retailer:"string"==typeof o.retailer?o.retailer:null,url:"string"==typeof o.product_url?o.product_url:null,price:gt(n.state),currency:"string"==typeof o.unit_of_measurement?o.unit_of_measurement:"string"==typeof o.currency?o.currency:"",inStock:null,discontinued:!0===o.discontinued,stockCount:"number"==typeof o.stock_count?o.stock_count:null,lastCheck:"string"==typeof o.last_check?o.last_check:null,history:mt(o.price_history),imageProxyUrl:null,imageBroken:!1,entityIds:{price:s}},l=e.get("photo");if(l){const e=t.states[l];if(e)if("unavailable"===e.state||"unknown"===e.state)a.imageBroken=!0;else{const t=e.attributes.entity_picture;"string"==typeof t&&t.length>0&&(a.imageProxyUrl=t)}}const c=e.get("in_stock");if(c){const e=t.states[c];e&&(a.inStock=_t(e.state),a.entityIds.inStock=c)}const d=e.get("discontinued");if(d){const e=t.states[d];if(e){const t=_t(e.state);null!=t&&(a.discontinued=t),a.entityIds.discontinued=d}}return a}function xt(t,e,r,i=2){if(t.length<2)return"";const s=t.length>=4?wt(t):t;if(s.length<2)return"";const n=s.map(t=>t.price),o=Math.min(...n),a=Math.max(...n)-o||1,l=r-2*i,c=e/(s.length-1);let d="";return s.forEach((t,e)=>{const s=e*c,n=r-i-(t.price-o)/a*l;d+=0===e?`M ${s.toFixed(2)} ${n.toFixed(2)}`:` L ${s.toFixed(2)} ${n.toFixed(2)}`}),d}function wt(t,e=5){if(t.length<2)return t;const r=t.map(t=>t.price),i=kt(r),s=r.map(t=>Math.abs(t-i)),n=kt(s);return 0===n?t:t.filter(t=>Math.abs(t.price-i)<=e*n)}function kt(t){const e=[...t].sort((t,e)=>t-e),r=Math.floor(e.length/2);return e.length%2==0?(e[r-1]+e[r])/2:e[r]}let At=class extends at{constructor(){super(...arguments),this.refreshingAlternatives=!1,this.handleRefresh=t=>{t.stopPropagation(),this.refreshingAlternatives||this.onRefreshAlternatives?.(this.product)}}get headlinePrice(){const{product:t}=this;return null!=t.priceLocal&&t.localCurrency?{value:t.priceLocal,currency:t.localCurrency}:t.discontinued&&null!=t.lastKnownPrice?{value:t.lastKnownPrice,currency:t.lastKnownCurrency??t.currency}:{value:t.price,currency:t.currency||null}}get sourcePriceLine(){const{product:t}=this;return null!=t.priceLocal&&t.localCurrency?t.currency===t.localCurrency?V:ft(t.price,t.currency):V}get priceDelta(){const{product:t}=this;if(null==t.price)return null;const e=t.price;for(let r=t.history.length-1;r>=0;r--){const i=t.history[r].price;if(i!==e)return{amount:Math.abs(e-i),direction:e>i?"up":"down"}}return null}renderDelta(){const t=this.priceDelta;if(null==t)return V;const e="up"===t.direction?"↑":"↓",r="up"===t.direction?"delta delta--up":"delta delta--down";return F`<span class=${r}>${e} ${ft(t.amount,null)}</span>`}renderImage(){const{product:t}=this,e=t.imageProxyUrl??(t.imageBroken?null:t.imageUrl);return e?F`<img
      class="image"
      src=${e}
      alt=${t.title}
      loading="lazy"
    />`:F`<div class="image image--placeholder" role="img" aria-label="No image">
        <ha-icon icon="mdi:tag-search"></ha-icon>
      </div>`}renderSparkline(){const{product:t}=this;if(t.history.length<2)return V;const e=xt(t.history,280,48);return e?F`<svg
      class="sparkline"
      viewBox="0 0 ${280} ${48}"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d=${e} fill="none" stroke="currentColor" stroke-width="1.5" />
    </svg>`:V}renderStatusChips(){const{product:t}=this,e=[];return t.discontinued?e.push(F`<span class="chip chip--warn" title=${t.discontinuedReason??""}>
        Discontinued
      </span>`):!1===t.inStock?e.push(F`<span class="chip chip--warn">Out of stock</span>`):!0===t.inStock&&e.push(F`<span class="chip chip--ok">In stock</span>`),null!=t.stockCount&&t.stockCount>0&&e.push(F`<span class="chip">${t.stockCount} units</span>`),t.retailer&&e.push(F`<span class="chip chip--retailer">${t.retailer}</span>`),e.length?F`<div class="chips">${e}</div>`:V}get cleanedExtremes(){const{product:t}=this;if(t.history.length>=4){const e=wt(t.history);if(e.length>=2){const t=e.map(t=>t.price);return{low:Math.min(...t),high:Math.max(...t)}}}return{low:t.lowest,high:t.highest}}renderAlternatives(){const{product:t}=this,e=t.alternatives.length>0,r=null!=t.alternativesError,i=null!=t.alternativesFetchedAt;return F`
      <section class="alts">
        <div class="alts__header">
          <span class="alts__title">
            ${e?F`Alternatives <span class="alts__count">${t.alternatives.length}</span>`:F`Alternatives`}
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
        ${r?F`<p class="alts__error">${t.alternativesError}</p>`:V}
        ${e?F`<ul class="alts__list">
              ${t.alternatives.map(t=>this.renderAlternative(t))}
            </ul>`:r||this.refreshingAlternatives?V:F`<p class="alts__empty">
              ${i?"No alternatives found.":"Click refresh to search for alternatives."}
            </p>`}
      </section>
    `}renderAlternative(t){const{product:e}=this;let r=null,i="alts__price";return null!=t.price&&null!=e.price&&t.currency===e.currency&&(r=t.price-e.price,r<0?i="alts__price alts__price--cheaper":r>0&&(i="alts__price alts__price--pricier")),F`
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
              ${t.retailer?F`<span>${t.retailer}</span>`:V}
              ${t.confidence>0?F`<span class="alts__confidence" title="Match confidence">
                    ${Math.round(100*t.confidence)}%
                  </span>`:V}
              ${!0===t.shipsToUserRegion?F`<span class="alts__ships alts__ships--yes" title="Likely ships to your region">
                    ✓ ships
                  </span>`:!1===t.shipsToUserRegion?F`<span class="alts__ships alts__ships--no" title="Likely does not ship to your region">
                    ✗ no ship
                  </span>`:V}
            </span>
          </div>
          <div class=${i}>
            ${null!=t.price?ft(t.price,t.currency):F`<span class="alts__price-unknown">—</span>`}
          </div>
        </a>
      </li>
    `}renderStatRow(){const{product:t}=this,e=[];if(null!=t.targetPrice){const r=null!=t.targetDiff&&t.targetDiff<=0?"stat__value stat__value--good":"stat__value";e.push(F`<div class="stat">
        <span class="stat__label">Target</span>
        <span class=${r}>${ft(t.targetPrice,t.currency)}</span>
      </div>`)}return e.length?F`<div class="stats">${e}</div>`:V}renderListings(){const{product:t}=this;return 0===t.listings.length?V:F`
      <section class="listings">
        <div class="listings__header">
          <span class="listings__title">
            Listings <span class="listings__count">${t.listings.length}</span>
          </span>
        </div>
        <ul class="listings__list">
          ${t.listings.map(t=>this.renderListingRow(t))}
        </ul>
      </section>
    `}renderListingRow(t){const e=xt(t.history,80,24,2),r=t.discontinued?F`<span class="listings__chip listings__chip--warn">disc.</span>`:!1===t.inStock?F`<span class="listings__chip listings__chip--warn">out</span>`:!0===t.inStock?F`<span class="listings__chip listings__chip--ok">in stock</span>`:V,i=t.imageProxyUrl?F`<img
          class="listings__thumb"
          src=${t.imageProxyUrl}
          alt=""
          loading="lazy"
        />`:F`<span
          class="listings__thumb listings__thumb--placeholder"
          aria-hidden="true"
        ></span>`,s=F`
      ${i}
      <div class="listings__info">
        <span class="listings__row-retailer">
          ${t.retailer??"Unknown"}
          ${t.isPrimary?F`<span class="listings__badge">primary</span>`:V}
        </span>
        <span class="listings__row-meta">
          ${r}
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
        ${t.isPrimary?V:F`<button
              class="listings__remove"
              type="button"
              @click=${e=>this.handleRemoveListing(e,t)}
              aria-label=${`Remove ${t.retailer??"listing"}`}
              title=${`Remove ${t.retailer??"this listing"}`}
            >
              ×
            </button>`}
      </li>
    `}handleRemoveListing(t,e){if(t.stopPropagation(),t.preventDefault(),e.isPrimary)return;const r=e.retailer?`Remove the ${e.retailer} listing from ${this.product.title}?`:`Remove this listing from ${this.product.title}?`;window.confirm(r)&&this.onRemoveListing?.(this.product,e)}handleClick(t){t.target.closest("a")||this.onOpen?.(this.product)}render(){const{product:t}=this,{value:e,currency:r}=this.headlinePrice,i=this.sourcePriceLine;return F`
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
            <div class="price">${ft(e,r)}</div>
            ${i===V?this.renderDelta():F`<div class="price-sub">${i} ${this.renderDelta()}</div>`}
          </div>

          ${this.renderSparkline()}
          ${this.renderStatRow()}
          ${this.renderListings()}
          ${this.renderAlternatives()}

          ${t.discontinued&&t.discontinuedReason?F`<p class="discontinued-reason">${t.discontinuedReason}</p>`:V}

          <footer class="footer">
            <span class="last-check">
              Last check: ${yt(t.lastCheck)}
            </span>
            ${t.url?F`<a class="link" href=${t.url} target="_blank" rel="noopener">
                  Open at retailer ↗
                </a>`:V}
          </footer>
        </div>
      </article>
    `}};At.styles=o`
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
  `,t([ht({attribute:!1})],At.prototype,"product",void 0),t([ht({attribute:!1})],At.prototype,"onOpen",void 0),t([ht({attribute:!1})],At.prototype,"onRefreshAlternatives",void 0),t([ht({type:Boolean,attribute:!1})],At.prototype,"refreshingAlternatives",void 0),t([ht({attribute:!1})],At.prototype,"onRemoveListing",void 0),At=t([ct("price-watch-card")],At);let PriceWatchPanel=class extends at{constructor(){super(...arguments),this._products=[],this._registry=null,this._registryError=null,this._connected=!1,this._refreshingEntries=new Set,this._conn=null,this._states={},this._handleOpen=t=>{t.url&&window.open(t.url,"_blank","noopener,noreferrer")},this._handleRefreshAlternatives=async t=>{if(this._conn&&!this._refreshingEntries.has(t.entryId)){this._refreshingEntries=new Set([...this._refreshingEntries,t.entryId]);try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"find_alternatives",service_data:{entry_id:t.entryId}})}catch(t){console.error("[price-watch-panel] find_alternatives failed:",t)}finally{const e=new Set(this._refreshingEntries);e.delete(t.entryId),this._refreshingEntries=e}}},this._handleRemoveListing=async(t,e)=>{if(this._conn)if(e.isPrimary)console.warn("[price-watch-panel] refusing to remove primary listing",e.listingId);else try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"remove_listing",service_data:{entry_id:t.entryId,listing_id:e.listingId}})}catch(t){console.error("[price-watch-panel] remove_listing failed:",t)}},this._handleAddProduct=()=>{window.history.pushState(null,"","/config/integrations/dashboard/add?domain=price_watch"),window.dispatchEvent(new CustomEvent("location-changed"))}}connectedCallback(){super.connectedCallback(),this._bootstrap()}disconnectedCallback(){super.disconnectedCallback(),this._unsubState?.(),this._unsubRegistry?.(),this._unsubState=void 0,this._unsubRegistry=void 0}async _bootstrap(){const t=window.hassConnection;if(!t)return void(this._registryError="Home Assistant WebSocket connection not available on this page. Try reloading.");let e;try{const r=await t;e=r.conn,this._conn=e,this._connected=!0}catch(t){const e=t instanceof Error?t.message:String(t);return void(this._registryError=`Could not open HA connection: ${e}`)}try{await this._fetchRegistry(e),await this._fetchInitialStates(e),this._unsubState=await e.subscribeEvents(t=>this._onStateChanged(t),"state_changed"),this._unsubRegistry=await e.subscribeEvents(()=>{this._fetchRegistry(e).then(()=>this._fetchInitialStates(e))},"entity_registry_updated")}catch(t){const e=t instanceof Error?t.message:String(t);this._registryError=`Setup failed after connection: ${e}`,console.error("[price-watch-panel]",t)}}async _fetchRegistry(t){const e=await t.sendMessagePromise({type:"config/entity_registry/list"}),r=new Map;for(const t of e)"price_watch"===t.platform&&r.set(t.unique_id,t.entity_id);this._registry={byUniqueId:r},this._registryError=null,this._rebuildProducts()}async _fetchInitialStates(t){if(!this._registry)return;const e=new Set(this._registry.byUniqueId.values()),r=await t.sendMessagePromise({type:"get_states"}),i={};for(const t of r)e.has(t.entity_id)&&(i[t.entity_id]=t);this._states=i,this._rebuildProducts()}_onStateChanged(t){const{entity_id:e,new_state:r}=t.data;if(!this._registry)return;new Set(this._registry.byUniqueId.values()).has(e)&&(null===r?delete this._states[e]:this._states={...this._states,[e]:r},this._rebuildProducts())}_rebuildProducts(){if(!this._registry)return void(this._products=[]);const t={states:this._states};this._products=function(t,e){const r=new Map;for(const[t,i]of e.byUniqueId){const e=bt(t);if(!e)continue;let s=r.get(e.entryId);if(s||(s={legacy:new Map,listings:new Map},r.set(e.entryId,s)),null===e.listingId)s.legacy.set(e.key,i);else{let t=s.listings.get(e.listingId);t||(t=new Map,s.listings.set(e.listingId,t)),t.set(e.key,i)}}const i=[];for(const[e,s]of r){const r=s.legacy,n=r.get("price");if(!n)continue;const o=t.states[n];if(!o)continue;const a=o.attributes,l={entryId:e,title:String(a.title??a.friendly_name??"Unknown product"),url:String(a.product_url??""),retailer:"string"==typeof a.retailer?a.retailer:null,imageUrl:"string"==typeof a.image_url?a.image_url:null,imageProxyUrl:null,imageBroken:!1,price:gt(o.state),currency:"string"==typeof a.unit_of_measurement?a.unit_of_measurement:"string"==typeof a.currency?a.currency:"",priceLocal:null,localCurrency:null,lowest:null,highest:null,targetDiff:null,targetPrice:"number"==typeof a.target_price?a.target_price:null,inStock:null,stockCount:"number"==typeof a.stock_count?a.stock_count:null,discontinued:!0===a.discontinued,discontinuedReason:"string"==typeof a.discontinued_reason?a.discontinued_reason:null,discontinuedAt:"string"==typeof a.discontinued_at?a.discontinued_at:null,lastKnownPrice:"number"==typeof a.last_known_price?a.last_known_price:null,lastKnownCurrency:"string"==typeof a.last_known_currency?a.last_known_currency:null,lastCheck:"string"==typeof a.last_check?a.last_check:null,history:mt(a.price_history),alternatives:vt(a.alternatives),alternativesFetchedAt:"string"==typeof a.alternatives_fetched_at?a.alternatives_fetched_at:null,alternativesError:"string"==typeof a.alternatives_error&&a.alternatives_error?a.alternatives_error:null,entityIds:{price:n},listings:[]},c=[["price_local",t=>{l.priceLocal=gt(t.state),l.localCurrency="string"==typeof t.attributes.unit_of_measurement?t.attributes.unit_of_measurement:null,l.entityIds.priceLocal=t.entity_id}],["lowest",t=>{l.lowest=gt(t.state),l.entityIds.lowest=t.entity_id}],["highest",t=>{l.highest=gt(t.state),l.entityIds.highest=t.entity_id}],["target_diff",t=>{l.targetDiff=gt(t.state),l.entityIds.targetDiff=t.entity_id}],["stock_count",t=>{l.stockCount=gt(t.state),l.entityIds.stockCount=t.entity_id}],["in_stock",t=>{l.inStock=_t(t.state),l.entityIds.inStock=t.entity_id}],["discontinued",t=>{const e=_t(t.state);null!=e&&(l.discontinued=e),l.entityIds.discontinued=t.entity_id}],["photo",t=>{if("unavailable"===t.state||"unknown"===t.state)return void(l.imageBroken=!0);const e=t.attributes.entity_picture;"string"==typeof e&&e.length>0&&(l.imageProxyUrl=e)}]];for(const[e,i]of c){const s=r.get(e);if(!s)continue;const n=t.states[s];n&&i(n)}const d="string"==typeof a.listing_id&&a.listing_id?a.listing_id:`l_${e.slice(-12).toLowerCase()}`,p=$t(t,s.legacy,d,!0);p&&l.listings.push(p);for(const[e,r]of s.listings){const i=$t(t,r,e,!1);i&&l.listings.push(i)}i.push(l)}return i.sort((t,e)=>t.discontinued!==e.discontinued?t.discontinued?1:-1:t.title.localeCompare(e.title)),i}(t,this._registry)}_renderHeader(){const t=this._products.length,e=this._products.filter(t=>t.discontinued).length;return F`
      <header class="panel-header">
        <div class="panel-header__title">
          <h1>Price Watch</h1>
          <div class="panel-header__counts">
            ${t-e} active${e>0?F` · ${e} discontinued`:V}
          </div>
        </div>
        <button class="add-button" @click=${this._handleAddProduct}>
          + Add product
        </button>
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
              .onRemoveListing=${this._handleRemoveListing}
            ></price-watch-card>
          `)}
      </div>
    `}render(){return F`
      <div class="panel">
        ${this._renderHeader()}
        ${this._registryError?this._renderError():this._connected&&this._registry?0===this._products.length?this._renderEmptyState():this._renderGrid():this._renderLoading()}
      </div>
    `}};PriceWatchPanel.styles=o`
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
  `,t([ut()],PriceWatchPanel.prototype,"_products",void 0),t([ut()],PriceWatchPanel.prototype,"_registry",void 0),t([ut()],PriceWatchPanel.prototype,"_registryError",void 0),t([ut()],PriceWatchPanel.prototype,"_connected",void 0),t([ut()],PriceWatchPanel.prototype,"_refreshingEntries",void 0),PriceWatchPanel=t([ct("price-watch-panel")],PriceWatchPanel);export{PriceWatchPanel};
