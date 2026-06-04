function e(e,t,r,i){var s,o=arguments.length,a=o<3?t:null===i?i=Object.getOwnPropertyDescriptor(t,r):i;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)a=Reflect.decorate(e,t,r,i);else for(var n=e.length-1;n>=0;n--)(s=e[n])&&(a=(o<3?s(a):o>3?s(t,r,a):s(t,r))||a);return o>3&&a&&Object.defineProperty(t,r,a),a}"function"==typeof SuppressedError&&SuppressedError;const t=globalThis,r=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,i=Symbol(),s=new WeakMap;let o=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(r&&void 0===e){const r=void 0!==t&&1===t.length;r&&(e=s.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),r&&s.set(t,e))}return e}toString(){return this.cssText}};const a=(e,...t)=>{const r=1===e.length?e[0]:t.reduce((t,r,i)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+e[i+1],e[0]);return new o(r,e,i)},n=r?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const r of e.cssRules)t+=r.cssText;return(e=>new o("string"==typeof e?e:e+"",void 0,i))(t)})(e):e,{is:l,defineProperty:c,getOwnPropertyDescriptor:d,getOwnPropertyNames:p,getOwnPropertySymbols:h,getPrototypeOf:_}=Object,u=globalThis,g=u.trustedTypes,v=g?g.emptyScript:"",f=u.reactiveElementPolyfillSupport,m=(e,t)=>e,y={toAttribute(e,t){switch(t){case Boolean:e=e?v:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let r=e;switch(t){case Boolean:r=null!==e;break;case Number:r=null===e?null:Number(e);break;case Object:case Array:try{r=JSON.parse(e)}catch(e){r=null}}return r}},b=(e,t)=>!l(e,t),x={attribute:!0,type:String,converter:y,reflect:!1,useDefault:!1,hasChanged:b};Symbol.metadata??=Symbol("metadata"),u.litPropertyMetadata??=new WeakMap;let k=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=x){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const r=Symbol(),i=this.getPropertyDescriptor(e,r,t);void 0!==i&&c(this.prototype,e,i)}}static getPropertyDescriptor(e,t,r){const{get:i,set:s}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:i,set(t){const o=i?.call(this);s?.call(this,t),this.requestUpdate(e,o,r)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??x}static _$Ei(){if(this.hasOwnProperty(m("elementProperties")))return;const e=_(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(m("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m("properties"))){const e=this.properties,t=[...p(e),...h(e)];for(const r of t)this.createProperty(r,e[r])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,r]of t)this.elementProperties.set(e,r)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const r=this._$Eu(e,t);void 0!==r&&this._$Eh.set(r,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const r=new Set(e.flat(1/0).reverse());for(const e of r)t.unshift(n(e))}else void 0!==e&&t.push(n(e));return t}static _$Eu(e,t){const r=t.attribute;return!1===r?void 0:"string"==typeof r?r:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const r of t.keys())this.hasOwnProperty(r)&&(e.set(r,this[r]),delete this[r]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,i)=>{if(r)e.adoptedStyleSheets=i.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const r of i){const i=document.createElement("style"),s=t.litNonce;void 0!==s&&i.setAttribute("nonce",s),i.textContent=r.cssText,e.appendChild(i)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,r){this._$AK(e,r)}_$ET(e,t){const r=this.constructor.elementProperties.get(e),i=this.constructor._$Eu(e,r);if(void 0!==i&&!0===r.reflect){const s=(void 0!==r.converter?.toAttribute?r.converter:y).toAttribute(t,r.type);this._$Em=e,null==s?this.removeAttribute(i):this.setAttribute(i,s),this._$Em=null}}_$AK(e,t){const r=this.constructor,i=r._$Eh.get(e);if(void 0!==i&&this._$Em!==i){const e=r.getPropertyOptions(i),s="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:y;this._$Em=i;const o=s.fromAttribute(t,e.type);this[i]=o??this._$Ej?.get(i)??o,this._$Em=null}}requestUpdate(e,t,r,i=!1,s){if(void 0!==e){const o=this.constructor;if(!1===i&&(s=this[e]),r??=o.getPropertyOptions(e),!((r.hasChanged??b)(s,t)||r.useDefault&&r.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(o._$Eu(e,r))))return;this.C(e,t,r)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:r,reflect:i,wrapped:s},o){r&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,o??t??this[e]),!0!==s||void 0!==o)||(this._$AL.has(e)||(this.hasUpdated||r||(t=void 0),this._$AL.set(e,t)),!0===i&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,r]of e){const{wrapped:e}=r,i=this[t];!0!==e||this._$AL.has(t)||void 0===i||this.C(t,void 0,r,i)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};k.elementStyles=[],k.shadowRootOptions={mode:"open"},k[m("elementProperties")]=new Map,k[m("finalized")]=new Map,f?.({ReactiveElement:k}),(u.reactiveElementVersions??=[]).push("2.1.2");const $=globalThis,w=e=>e,S=$.trustedTypes,E=S?S.createPolicy("lit-html",{createHTML:e=>e}):void 0,A="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,C="?"+P,T=`<${C}>`,z=document,I=()=>z.createComment(""),N=e=>null===e||"object"!=typeof e&&"function"!=typeof e,R=Array.isArray,O="[ \t\n\f\r]",L=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,M=/-->/g,H=/>/g,U=RegExp(`>|${O}(?:([^\\s"'>=/]+)(${O}*=${O}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),D=/'/g,B=/"/g,j=/^(?:script|style|textarea|title)$/i,F=(e=>(t,...r)=>({_$litType$:e,strings:t,values:r}))(1),K=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),q=new WeakMap,W=z.createTreeWalker(z,129);function Y(e,t){if(!R(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==E?E.createHTML(t):t}const G=(e,t)=>{const r=e.length-1,i=[];let s,o=2===t?"<svg>":3===t?"<math>":"",a=L;for(let t=0;t<r;t++){const r=e[t];let n,l,c=-1,d=0;for(;d<r.length&&(a.lastIndex=d,l=a.exec(r),null!==l);)d=a.lastIndex,a===L?"!--"===l[1]?a=M:void 0!==l[1]?a=H:void 0!==l[2]?(j.test(l[2])&&(s=RegExp("</"+l[2],"g")),a=U):void 0!==l[3]&&(a=U):a===U?">"===l[0]?(a=s??L,c=-1):void 0===l[1]?c=-2:(c=a.lastIndex-l[2].length,n=l[1],a=void 0===l[3]?U:'"'===l[3]?B:D):a===B||a===D?a=U:a===M||a===H?a=L:(a=U,s=void 0);const p=a===U&&e[t+1].startsWith("/>")?" ":"";o+=a===L?r+T:c>=0?(i.push(n),r.slice(0,c)+A+r.slice(c)+P+p):r+P+(-2===c?t:p)}return[Y(e,o+(e[r]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),i]};class J{constructor({strings:e,_$litType$:t},r){let i;this.parts=[];let s=0,o=0;const a=e.length-1,n=this.parts,[l,c]=G(e,t);if(this.el=J.createElement(l,r),W.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(i=W.nextNode())&&n.length<a;){if(1===i.nodeType){if(i.hasAttributes())for(const e of i.getAttributeNames())if(e.endsWith(A)){const t=c[o++],r=i.getAttribute(e).split(P),a=/([.?@])?(.*)/.exec(t);n.push({type:1,index:s,name:a[2],strings:r,ctor:"."===a[1]?te:"?"===a[1]?re:"@"===a[1]?ie:ee}),i.removeAttribute(e)}else e.startsWith(P)&&(n.push({type:6,index:s}),i.removeAttribute(e));if(j.test(i.tagName)){const e=i.textContent.split(P),t=e.length-1;if(t>0){i.textContent=S?S.emptyScript:"";for(let r=0;r<t;r++)i.append(e[r],I()),W.nextNode(),n.push({type:2,index:++s});i.append(e[t],I())}}}else if(8===i.nodeType)if(i.data===C)n.push({type:2,index:s});else{let e=-1;for(;-1!==(e=i.data.indexOf(P,e+1));)n.push({type:7,index:s}),e+=P.length-1}s++}}static createElement(e,t){const r=z.createElement("template");return r.innerHTML=e,r}}function Q(e,t,r=e,i){if(t===K)return t;let s=void 0!==i?r._$Co?.[i]:r._$Cl;const o=N(t)?void 0:t._$litDirective$;return s?.constructor!==o&&(s?._$AO?.(!1),void 0===o?s=void 0:(s=new o(e),s._$AT(e,r,i)),void 0!==i?(r._$Co??=[])[i]=s:r._$Cl=s),void 0!==s&&(t=Q(e,s._$AS(e,t.values),s,i)),t}class Z{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:r}=this._$AD,i=(e?.creationScope??z).importNode(t,!0);W.currentNode=i;let s=W.nextNode(),o=0,a=0,n=r[0];for(;void 0!==n;){if(o===n.index){let t;2===n.type?t=new X(s,s.nextSibling,this,e):1===n.type?t=new n.ctor(s,n.name,n.strings,this,e):6===n.type&&(t=new se(s,this,e)),this._$AV.push(t),n=r[++a]}o!==n?.index&&(s=W.nextNode(),o++)}return W.currentNode=z,i}p(e){let t=0;for(const r of this._$AV)void 0!==r&&(void 0!==r.strings?(r._$AI(e,r,t),t+=r.strings.length-2):r._$AI(e[t])),t++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,r,i){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=r,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=Q(this,e,t),N(e)?e===V||null==e||""===e?(this._$AH!==V&&this._$AR(),this._$AH=V):e!==this._$AH&&e!==K&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>R(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==V&&N(this._$AH)?this._$AA.nextSibling.data=e:this.T(z.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:r}=e,i="number"==typeof r?this._$AC(e):(void 0===r.el&&(r.el=J.createElement(Y(r.h,r.h[0]),this.options)),r);if(this._$AH?._$AD===i)this._$AH.p(t);else{const e=new Z(i,this),r=e.u(this.options);e.p(t),this.T(r),this._$AH=e}}_$AC(e){let t=q.get(e.strings);return void 0===t&&q.set(e.strings,t=new J(e)),t}k(e){R(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let r,i=0;for(const s of e)i===t.length?t.push(r=new X(this.O(I()),this.O(I()),this,this.options)):r=t[i],r._$AI(s),i++;i<t.length&&(this._$AR(r&&r._$AB.nextSibling,i),t.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=w(e).nextSibling;w(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class ee{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,r,i,s){this.type=1,this._$AH=V,this._$AN=void 0,this.element=e,this.name=t,this._$AM=i,this.options=s,r.length>2||""!==r[0]||""!==r[1]?(this._$AH=Array(r.length-1).fill(new String),this.strings=r):this._$AH=V}_$AI(e,t=this,r,i){const s=this.strings;let o=!1;if(void 0===s)e=Q(this,e,t,0),o=!N(e)||e!==this._$AH&&e!==K,o&&(this._$AH=e);else{const i=e;let a,n;for(e=s[0],a=0;a<s.length-1;a++)n=Q(this,i[r+a],t,a),n===K&&(n=this._$AH[a]),o||=!N(n)||n!==this._$AH[a],n===V?e=V:e!==V&&(e+=(n??"")+s[a+1]),this._$AH[a]=n}o&&!i&&this.j(e)}j(e){e===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class te extends ee{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===V?void 0:e}}class re extends ee{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==V)}}class ie extends ee{constructor(e,t,r,i,s){super(e,t,r,i,s),this.type=5}_$AI(e,t=this){if((e=Q(this,e,t,0)??V)===K)return;const r=this._$AH,i=e===V&&r!==V||e.capture!==r.capture||e.once!==r.once||e.passive!==r.passive,s=e!==V&&(r===V||i);i&&this.element.removeEventListener(this.name,this,r),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class se{constructor(e,t,r){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=r}get _$AU(){return this._$AM._$AU}_$AI(e){Q(this,e)}}const oe=$.litHtmlPolyfillSupport;oe?.(J,X),($.litHtmlVersions??=[]).push("3.3.3");const ae=globalThis;class ne extends k{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,r)=>{const i=r?.renderBefore??t;let s=i._$litPart$;if(void 0===s){const e=r?.renderBefore??null;i._$litPart$=s=new X(t.insertBefore(I(),e),e,void 0,r??{})}return s._$AI(e),s})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return K}}ne._$litElement$=!0,ne.finalized=!0,ae.litElementHydrateSupport?.({LitElement:ne});const le=ae.litElementPolyfillSupport;le?.({LitElement:ne}),(ae.litElementVersions??=[]).push("4.2.2");const ce={attribute:!0,type:String,converter:y,reflect:!1,hasChanged:b},de=(e=ce,t,r)=>{const{kind:i,metadata:s}=r;let o=globalThis.litPropertyMetadata.get(s);if(void 0===o&&globalThis.litPropertyMetadata.set(s,o=new Map),"setter"===i&&((e=Object.create(e)).wrapped=!0),o.set(r.name,e),"accessor"===i){const{name:i}=r;return{set(r){const s=t.get.call(this);t.set.call(this,r),this.requestUpdate(i,s,e,!0,r)},init(t){return void 0!==t&&this.C(i,void 0,e,t),t}}}if("setter"===i){const{name:i}=r;return function(r){const s=this[i];t.call(this,r),this.requestUpdate(i,s,e,!0,r)}}throw Error("Unsupported decorator location: "+i)};function pe(e){return(t,r)=>"object"==typeof r?de(e,t,r):((e,t,r)=>{const i=t.hasOwnProperty(r);return t.constructor.createProperty(r,e),i?Object.getOwnPropertyDescriptor(t,r):void 0})(e,t,r)}function he(e){return pe({...e,state:!0,attribute:!1})}function _e(e){if(null==e||"unknown"===e||"unavailable"===e)return null;const t=Number(e);return Number.isFinite(t)?t:null}function ue(e){return null==e||"unknown"===e||"unavailable"===e?null:"on"===e||"true"===e||"off"!==e&&"false"!==e&&null}function ge(e,t,r="en"){if(null==e)return"—";if(!t)return e.toLocaleString(r);try{return new Intl.NumberFormat(r,{style:"currency",currency:t,maximumFractionDigits:2}).format(e)}catch{return`${e.toLocaleString(r,{maximumFractionDigits:2})} ${t}`}}function ve(e,t="en"){if(!e)return"never";const r=new Date(e).getTime();if(Number.isNaN(r))return e;const i=Date.now()-r,s=Math.round(i/1e3),o=Math.abs(s),a=new Intl.RelativeTimeFormat(t,{numeric:"auto"});return o<60?a.format(-s,"second"):o<3600?a.format(-Math.round(s/60),"minute"):o<86400?a.format(-Math.round(s/3600),"hour"):o<2592e3?a.format(-Math.round(s/86400),"day"):a.format(-Math.round(s/2592e3),"month")}function fe(e){if(!Array.isArray(e))return[];const t=[];for(const r of e)if(null!=r&&"object"==typeof r&&"price"in r&&"ts"in r){const e=r,i="number"==typeof e.price?e.price:null;if(null==i)continue;t.push({ts:String(e.ts??""),price:i,currency:String(e.currency??""),in_stock:!1!==e.in_stock})}return t}function me(e){if(!Array.isArray(e))return[];const t=[];for(const r of e){if(!r||"object"!=typeof r)continue;const e=r,i="string"==typeof e.title?e.title:"",s="string"==typeof e.url?e.url:"";i&&s&&t.push({title:i,url:s,price:"number"==typeof e.price?e.price:null,currency:"string"==typeof e.currency?e.currency:"",retailer:"string"==typeof e.retailer?e.retailer:"",imageUrl:"string"==typeof e.image_url&&e.image_url?e.image_url:null,confidence:"number"==typeof e.confidence?Math.max(0,Math.min(1,e.confidence)):0,notes:"string"==typeof e.notes?e.notes:"",shipsToUserRegion:"boolean"==typeof e.ships_to_user_region?e.ships_to_user_region:null})}return t.sort((e,t)=>{if(t.confidence!==e.confidence)return t.confidence-e.confidence;return(e.price??Number.POSITIVE_INFINITY)-(t.price??Number.POSITIVE_INFINITY)}),t}function ye(e){const t=e.indexOf("_");if(t<0)return null;const r=e.slice(0,t),i=e.slice(t+1),s=/^(l_[0-9a-z]+)_(.+)$/.exec(i);return s?{entryId:r,listingId:s[1],key:s[2]}:{entryId:r,listingId:null,key:i}}function be(e,t,r,i){const s=t.get("price");if(!s)return null;const o=e.states[s];if(!o)return null;const a=o.attributes,n={listingId:r,isPrimary:i,retailer:"string"==typeof a.retailer?a.retailer:null,url:"string"==typeof a.product_url?a.product_url:null,price:_e(o.state),currency:"string"==typeof a.unit_of_measurement?a.unit_of_measurement:"string"==typeof a.currency?a.currency:"",inStock:null,discontinued:!0===a.discontinued,stockCount:"number"==typeof a.stock_count?a.stock_count:null,lastCheck:"string"==typeof a.last_check?a.last_check:null,history:fe(a.price_history),imageProxyUrl:null,imageBroken:!1,shipsToUserRegion:"boolean"==typeof a.ships_to_user_region?a.ships_to_user_region:null,hasCookies:!0===a.has_cookies,entityIds:{price:s}},l=t.get("photo");if(l){const t=e.states[l];if(t)if("unavailable"===t.state||"unknown"===t.state)n.imageBroken=!0;else{const e=t.attributes.entity_picture;"string"==typeof e&&e.length>0&&(n.imageProxyUrl=e)}}const c=t.get("in_stock");if(c){const t=e.states[c];t&&(n.inStock=ue(t.state),n.entityIds.inStock=c)}const d=t.get("discontinued");if(d){const t=e.states[d];if(t){const e=ue(t.state);null!=e&&(n.discontinued=e),n.entityIds.discontinued=d}}return n}function xe(e,t=5){if(e.length<2)return e;const r=e.map(e=>e.price),i=ke(r),s=r.map(e=>Math.abs(e-i)),o=ke(s);return 0===o?e:e.filter(e=>Math.abs(e.price-i)<=t*o)}function ke(e){const t=[...e].sort((e,t)=>e-t),r=Math.floor(t.length/2);return t.length%2==0?(t[r-1]+t[r])/2:t[r]}class $e extends ne{constructor(){super(...arguments),this.refreshingAlternatives=!1,this.hideNonShipping=!1,this.refreshingNow=!1,this.handleRefresh=e=>{e.stopPropagation(),this.refreshingAlternatives||this.onRefreshAlternatives?.(this.product)},this.handleRefreshNow=e=>{e.stopPropagation(),this.refreshingNow||this.onRefreshNow?.(this.product)},this.handleTogglePaused=e=>{e.stopPropagation(),this.onSetPaused?.(this.product,!this.product.paused)},this.handleAlert=e=>{e.stopPropagation(),this.onAlert?.(this.product)},this.handleTargetCommit=e=>{e.stopPropagation();const t=e.target,r=t.value.trim(),i=""===r?null:Number(r);if(null!==i&&Number.isNaN(i))return void(t.value=null!=this.product.targetPrice?String(this.product.targetPrice):"");i!==this.product.targetPrice&&this.onSetTarget?.(this.product,i)},this.handleTargetKeydown=e=>{e.stopPropagation(),"Enter"===e.key&&e.target.blur()}}get headlinePrice(){const{product:e}=this;return null!=e.priceLocal&&e.localCurrency?{value:e.priceLocal,currency:e.localCurrency}:e.discontinued&&null!=e.lastKnownPrice?{value:e.lastKnownPrice,currency:e.lastKnownCurrency??e.currency}:{value:e.price,currency:e.currency||null}}get sourcePriceLine(){const{product:e}=this;return null!=e.priceLocal&&e.localCurrency?e.currency===e.localCurrency?V:ge(e.price,e.currency):V}get priceDelta(){const{product:e}=this;if(null==e.price)return null;const t=e.price;for(let r=e.history.length-1;r>=0;r--){const i=e.history[r].price;if(i!==t)return{amount:Math.abs(t-i),direction:t>i?"up":"down"}}return null}renderDelta(){const e=this.priceDelta;if(null==e)return V;const t="up"===e.direction?"↑":"↓",r="up"===e.direction?"delta delta--up":"delta delta--down";return F`<span class=${r}>${t} ${ge(e.amount,null)}</span>`}renderImage(){const{product:e}=this,t=e.imageProxyUrl??(e.imageBroken?null:e.imageUrl);return t?F`<img
      class="image"
      src=${t}
      alt=${e.title}
      loading="lazy"
    />`:F`<div class="image image--placeholder" role="img" aria-label="No image">
        <ha-icon icon="mdi:tag-search"></ha-icon>
      </div>`}renderSparkline(){const{product:e}=this;if(e.history.length<2)return V;const t=function(e,t,r,i=2){if(e.length<2)return"";const s=e.length>=4?xe(e):e;if(s.length<2)return"";const o=s.map(e=>e.price),a=Math.min(...o),n=Math.max(...o)-a||1,l=r-2*i,c=t/(s.length-1);let d="";return s.forEach((e,t)=>{const s=t*c,o=r-i-(e.price-a)/n*l;d+=0===t?`M ${s.toFixed(2)} ${o.toFixed(2)}`:` L ${s.toFixed(2)} ${o.toFixed(2)}`}),d}(e.history,280,48);return t?F`<svg
      class="sparkline"
      viewBox="0 0 ${280} ${48}"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d=${t} fill="none" stroke="currentColor" stroke-width="1.5" />
    </svg>`:V}renderStatusChips(){const{product:e}=this,t=[];return e.paused&&t.push(F`<span class="chip chip--paused" title="Polling paused">
        Paused
      </span>`),e.discontinued?t.push(F`<span class="chip chip--warn" title=${e.discontinuedReason??""}>
        Discontinued
      </span>`):!1===e.inStock?t.push(F`<span class="chip chip--warn">Out of stock</span>`):!0===e.inStock&&t.push(F`<span class="chip chip--ok">In stock</span>`),null!=e.stockCount&&e.stockCount>0&&t.push(F`<span class="chip">${e.stockCount} units</span>`),e.retailer&&t.push(F`<span class="chip chip--retailer">${e.retailer}</span>`),t.length?F`<div class="chips">${t}</div>`:V}get cleanedExtremes(){const{product:e}=this;if(e.history.length>=4){const t=xe(e.history);if(t.length>=2){const e=t.map(e=>e.price);return{low:Math.min(...e),high:Math.max(...e)}}}return{low:e.lowest,high:e.highest}}renderAlternatives(){const{product:e}=this,t=null!=e.alternativesError,r=null!=e.alternativesFetchedAt,i=this.hideNonShipping?e.alternatives.filter(e=>!1!==e.shipsToUserRegion):e.alternatives,s=this.excludedAltHosts,o=s&&s.size>0?i.filter(e=>!s.has(this.altHost(e.url))):i,a=e.alternatives.length-o.length,n=o.length>0;return F`
      <section class="alts">
        <div class="alts__header">
          <span class="alts__title">
            ${n?F`Alternatives <span class="alts__count">${o.length}</span>`:F`Alternatives`}
          </span>
          <span class="alts__meta">
            ${r?ve(e.alternativesFetchedAt):""}
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
        ${t?F`<p class="alts__error">${e.alternativesError}</p>`:V}
        ${n?F`<ul class="alts__list">
              ${o.map(e=>this.renderAlternative(e))}
            </ul>`:t||this.refreshingAlternatives?V:F`<p class="alts__empty">
              ${r?a>0?"All alternatives were hidden (don't ship to your region).":"No alternatives found.":"Click refresh to search for alternatives."}
            </p>`}
        ${n&&a>0?F`<p class="alts__hidden-note">
              ${a} hidden (don't ship to your region)
            </p>`:V}
      </section>
    `}get listingUrls(){const e=e=>(e??"").trim().replace(/\/+$/,"").toLowerCase(),t=new Set;for(const r of this.product.listings){const i=e(r.url);i&&t.add(i)}return t}altHost(e){try{return new URL(e??"").hostname.replace(/^www\./i,"").toLowerCase()}catch{return""}}renderAlternative(e){const{product:t}=this;let r=null,i="alts__price";null!=e.price&&null!=t.price&&e.currency===t.currency&&(r=e.price-t.price,r<0?i="alts__price alts__price--cheaper":r>0&&(i="alts__price alts__price--pricier"));const s=(e.url??"").trim().replace(/\/+$/,"").toLowerCase(),o=""!==s&&this.listingUrls.has(s);return F`
      <li class="alts__row">
        <a
          class="alts__link"
          href=${e.url}
          target="_blank"
          rel="noopener noreferrer"
          @click=${e=>e.stopPropagation()}
          title=${e.notes||e.title}
        >
          <div class="alts__info">
            <span class="alts__row-title">${e.title}</span>
            <span class="alts__row-meta">
              ${e.retailer?F`<span>${e.retailer}</span>`:V}
              ${e.confidence>0?F`<span class="alts__confidence" title="Match confidence">
                    ${Math.round(100*e.confidence)}%
                  </span>`:V}
              ${!0===e.shipsToUserRegion?F`<span class="alts__ships alts__ships--yes" title="Likely ships to your region">
                    ✓ ships
                  </span>`:!1===e.shipsToUserRegion?F`<span class="alts__ships alts__ships--no" title="Likely does not ship to your region">
                    ✗ no ship
                  </span>`:V}
            </span>
          </div>
          <div class=${i}>
            ${null!=e.price?ge(e.price,e.currency):F`<span class="alts__price-unknown">—</span>`}
          </div>
        </a>
        ${this.onAddListing?o?F`<span
                class="alts__add alts__add--done"
                title="Already tracked as a listing"
                aria-label="Already a listing"
                >✓</span
              >`:F`<button
                class="alts__add"
                type="button"
                @click=${t=>this.handleAddListing(t,e)}
                aria-label=${`Add ${e.retailer||"this alternative"} as a listing`}
                title="Track this as a listing"
              >
                +
              </button>`:V}
        ${this.onExcludeAlternative?F`<button
              class="alts__exclude"
              type="button"
              @click=${t=>this.handleExcludeAlternative(t,e)}
              aria-label=${`Exclude ${this.altHost(e.url)||"this site"} from future results`}
              title=${`Exclude ${this.altHost(e.url)||"this site"} from searches`}
            >
              ⊘
            </button>`:V}
      </li>
    `}handleExcludeAlternative(e,t){e.stopPropagation(),e.preventDefault();const r=this.altHost(t.url);window.confirm(`Exclude ${r||"this site"} from all future searches and alternatives?`)&&this.onExcludeAlternative?.(this.product,t)}handleAddListing(e,t){e.stopPropagation(),e.preventDefault();const r=t.retailer?`Track the ${t.retailer} listing for ${this.product.title}?`:`Track this alternative as a listing on ${this.product.title}?`;window.confirm(r)&&this.onAddListing?.(this.product,t)}renderStoreAvailability(){const e=this.product.storeAvailability;if(!e||0===e.length)return V;const t=new Set(e.map(e=>e.store)).size,r=this.product.availableStores?.length??0,i=0===r,s=this.product.stockFromWarehouse,o=!i&&r<t?`${r}/${t} stores`:`${t} ${1===t?"store":"stores"}`,a=i?`Sold out · ${o}`:`In stock · ${o}${s?" · from Reykjavík":""}`,n=e.map(e=>{const t="sold_out"===e.status;return F`<span
        class=${t?"stores-d__store stores-d__store--out":"stores-d__store"}
        >${e.store}${e.fromWarehouse?F`<span class="stores-d__star" title="At the Reykjavík warehouse">*</span>`:V}</span
      >`});return F`<details
      class=${i?"stores-d stores-d--out":"stores-d stores-d--in"}
    >
      <summary class="stores-d__summary">
        <ha-icon
          icon=${i?"mdi:store-off-outline":"mdi:store-check-outline"}
        ></ha-icon>
        <span class="stores-d__label">${a}</span>
      </summary>
      <div class="stores-d__list">${n}</div>
      ${s?F`<div class="stores-d__hint">
            * stock is at the Reykjavík warehouse — stores outside the capital
            may need to order it in.
          </div>`:V}
    </details>`}renderSizeOptions(){const e=this.product.sizeOptions;return!e||e.length<2||!this.onChangeSize?V:F`<div class="sizes">
      <span class="sizes__label">Stærðir</span>
      <div class="sizes__chips">
        ${e.map(e=>e.selected?F`<span class="sizes__chip sizes__chip--on" aria-current="true"
                >${e.label}</span
              >`:F`<button
                type="button"
                class="sizes__chip"
                title=${`Track the ${e.label} size instead`}
                @click=${()=>this.onChangeSize?.(this.product,e.url,e.label)}
              >
                ${e.label}
              </button>`)}
      </div>
    </div>`}renderStatRow(){const{product:e}=this,t=[];if(null!=e.targetPrice){const r=null!=e.targetDiff&&e.targetDiff<=0?"stat__value stat__value--good":"stat__value";t.push(F`<div class="stat">
        <span class="stat__label">Target</span>
        <span class=${r}>${ge(e.targetPrice,e.currency)}</span>
      </div>`)}return t.length?F`<div class="stats">${t}</div>`:V}renderListings(){const{product:e}=this;if(0===e.listings.length)return V;const t=this.hideNonShipping?e.listings.filter(e=>e.isPrimary||!1!==e.shipsToUserRegion):e.listings,r=e.listings.length-t.length;return F`
      <section class="listings">
        <div class="listings__header">
          <span class="listings__title">
            Listings <span class="listings__count">${t.length}</span>
          </span>
        </div>
        <ul class="listings__list">
          ${t.map(e=>this.renderListingRow(e))}
        </ul>
        ${r>0?F`<p class="alts__hidden-note">
              ${r} hidden (don't ship to your region)
            </p>`:V}
      </section>
    `}renderListingRow(e){const t=e.discontinued?F`<span class="listings__chip listings__chip--warn">disc.</span>`:!1===e.inStock?F`<span class="listings__chip listings__chip--warn">out</span>`:!0===e.inStock?F`<span class="listings__chip listings__chip--ok">in stock</span>`:V,r=e.imageProxyUrl?F`<img
          class="listings__thumb"
          src=${e.imageProxyUrl}
          alt=""
          loading="lazy"
        />`:F`<span
          class="listings__thumb listings__thumb--placeholder"
          aria-hidden="true"
        ></span>`,i=F`
      ${r}
      <div class="listings__info">
        <span class="listings__row-retailer">
          <span class="listings__retailer-name"
            >${e.retailer??"Unknown"}</span
          >
          ${e.isPrimary?F`<span class="listings__badge">primary</span>`:V}
          ${!1===e.shipsToUserRegion?F`<span
                class="listings__badge listings__badge--noship"
                title="This retailer doesn't appear to ship to your region"
                >doesn't ship</span
              >`:V}
        </span>
        <span class="listings__row-meta">
          ${t}
          <span class="listings__last-check">
            ${ve(e.lastCheck)}
          </span>
        </span>
      </div>
      <div class="listings__price">
        ${ge(e.price,e.currency||null)}
      </div>
    `;return F`
      <li class="listings__row">
        ${e.url?F`<a
              class="listings__link"
              href=${e.url}
              target="_blank"
              rel="noopener noreferrer"
              @click=${e=>e.stopPropagation()}
              title=${e.retailer??e.url}
            >
              ${i}
            </a>`:F`<div class="listings__link listings__link--noUrl">${i}</div>`}
        <div class="listings__actions">
          ${this.onEditVariant?F`<button
                class="listings__edit"
                type="button"
                @click=${t=>this.handleEditVariant(t,e)}
                aria-label=${`Choose variant for ${e.retailer??"listing"}`}
                title="Track a specific product variant (e.g. with remote)"
              >
                ⚙
              </button>`:V}
          ${this.onEditListing?F`<button
                class="listings__edit"
                type="button"
                @click=${t=>this.handleEditListing(t,e)}
                aria-label=${`Edit price selector for ${e.retailer??"listing"}`}
                title="Advanced: set a custom price selector"
              >
                ✎
              </button>`:V}
          ${e.isPrimary?V:F`<button
                class="listings__remove"
                type="button"
                @click=${t=>this.handleRemoveListing(t,e)}
                aria-label=${`Remove ${e.retailer??"listing"}`}
                title=${`Remove ${e.retailer??"this listing"}`}
              >
                ×
              </button>`}
        </div>
      </li>
    `}handleEditListing(e,t){e.stopPropagation(),e.preventDefault(),this.onEditListing?.(this.product,t)}handleEditVariant(e,t){e.stopPropagation(),e.preventDefault(),this.onEditVariant?.(this.product,t)}handleRemoveListing(e,t){if(e.stopPropagation(),e.preventDefault(),t.isPrimary)return;const r=t.retailer?`Remove the ${t.retailer} listing from ${this.product.title}?`:`Remove this listing from ${this.product.title}?`;window.confirm(r)&&this.onRemoveListing?.(this.product,t)}renderActions(){if(!(this.onRefreshNow||this.onSetTarget||this.onSetPaused||this.onAlert))return V;const{product:e}=this;return F`
      <div class="actions" @click=${e=>e.stopPropagation()}>
        ${this.onSetTarget?F`<label class="actions__target" title="Notify when price drops to or below this">
              <span class="actions__target-label">Target</span>
              <input
                class="actions__target-input"
                type="number"
                inputmode="decimal"
                step="0.01"
                min="0"
                placeholder="—"
                .value=${null!=e.targetPrice?String(e.targetPrice):""}
                @change=${this.handleTargetCommit}
                @keydown=${this.handleTargetKeydown}
                @click=${e=>e.stopPropagation()}
              />
            </label>`:V}
        <div class="actions__spacer"></div>
        ${this.onAlert?F`<button
              class="actions__btn"
              type="button"
              @click=${this.handleAlert}
              aria-label="Create a price alert"
              title="Notify me (back in stock / target hit / price drop)"
            >
              <ha-icon icon="mdi:bell-plus-outline"></ha-icon>
            </button>`:V}
        ${this.onSetPaused?F`<button
              class="actions__btn"
              type="button"
              @click=${this.handleTogglePaused}
              aria-label=${e.paused?"Resume polling":"Pause polling"}
              title=${e.paused?"Resume polling":"Pause polling"}
            >
              <ha-icon icon=${e.paused?"mdi:play":"mdi:pause"}></ha-icon>
            </button>`:V}
        ${this.onRefreshNow?F`<button
              class="actions__btn"
              type="button"
              ?disabled=${this.refreshingNow}
              @click=${this.handleRefreshNow}
              aria-label="Refresh price now"
              title="Refresh price now"
            >
              <ha-icon
                icon=${this.refreshingNow?"mdi:loading":"mdi:refresh"}
                class=${this.refreshingNow?"actions__btn-spin":""}
              ></ha-icon>
            </button>`:V}
      </div>
    `}handleClick(e){e.target.closest("a")||this.onOpen?.(this.product)}handleKeydown(e){"Enter"!==e.key&&" "!==e.key||(e.preventDefault(),this.onOpen?.(this.product))}render(){const{product:e}=this,{value:t,currency:r}=this.headlinePrice,i=this.sourcePriceLine;return F`
      <article class="card ${e.discontinued?"card--faded":""}">
        <div
          class="card__open"
          @click=${this.handleClick}
          @keydown=${this.handleKeydown}
          tabindex="0"
          role="button"
          aria-label=${`Open ${e.title}`}
        >
          ${this.renderImage()}
          <header class="header">
            <h3 class="title">${e.title}</h3>
            ${this.renderStatusChips()}
          </header>
        </div>
        <div class="body">
          ${this.renderSizeOptions()}

          <div class="price-block">
            <div class="price">${ge(t,r)}</div>
            ${e.onSale&&null!=e.originalPrice?F`<div class="price-sale">
                    <span class="price-was"
                      >${ge(e.originalPrice,r)}</span
                    >
                    ${null!=e.discountPercent?F`<span class="price-off"
                          >−${e.discountPercent}%</span
                        >`:V}
                  </div>`:V}
            ${i===V?this.renderDelta():F`<div class="price-sub">${i} ${this.renderDelta()}</div>`}
          </div>

          ${this.renderSparkline()}
          ${this.renderStatRow()}
          ${this.renderStoreAvailability()}
          ${this.renderListings()}
          ${this.renderAlternatives()}

          ${e.discontinued&&e.discontinuedReason?F`<p class="discontinued-reason">${e.discontinuedReason}</p>`:V}

          ${this.renderActions()}

          <footer class="footer">
            <span class="last-check">
              Last check: ${ve(e.lastCheck)}
            </span>
            ${e.url?F`<a class="link" href=${e.url} target="_blank" rel="noopener">
                  Open at retailer ↗
                </a>`:V}
          </footer>
        </div>
      </article>
    `}}$e.styles=a`
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
      transition: transform 120ms ease, box-shadow 120ms ease;
      color: var(--primary-text-color, #212121);
    }
    /* Only the image + header open the product; the lift/affordance follows
       that region, not the whole card. */
    .card:has(.card__open:hover),
    .card:focus-within {
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    }
    .card__open {
      cursor: pointer;
      outline: none;
    }
    .card__open:focus-visible {
      outline: 2px solid var(--primary-color, #03a9f4);
      outline-offset: -2px;
    }
    .card__open:hover .title {
      text-decoration: underline;
      text-decoration-thickness: 1px;
      text-underline-offset: 2px;
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
      /* The header now lives in .card__open (outside .body), so it carries
         its own padding to sit flush under the full-bleed image. */
      padding: 14px 16px 0;
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
    .chip--paused {
      background: var(--secondary-text-color, #9e9e9e);
      color: #fff;
    }

    /* --- Per-card action bar --- */
    .actions {
      display: flex;
      align-items: center;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--divider-color, #e0e0e0);
    }
    .actions__spacer {
      flex: 1 1 auto;
    }
    .actions__target {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
    }
    .actions__target-label {
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .actions__target-input {
      width: 84px;
      box-sizing: border-box;
      padding: 4px 8px;
      font-size: 0.8rem;
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      outline: none;
    }
    .actions__target-input:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .actions__btn {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      cursor: pointer;
      color: var(--secondary-text-color, #757575);
      --mdc-icon-size: 18px;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .actions__btn:hover:not(:disabled) {
      color: var(--primary-color, #03a9f4);
      background: var(--secondary-background-color, #f5f5f5);
      border-color: var(--divider-color, #e0e0e0);
    }
    .actions__btn:disabled {
      cursor: wait;
      opacity: 0.6;
    }
    .actions__btn-spin {
      animation: alts-spin 1.2s linear infinite;
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
    /* On-sale: struck "was" price + a red "−N%" pill next to the headline. */
    .price-sale {
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
    }
    .price-was {
      font-size: 0.85rem;
      color: var(--secondary-text-color, #9e9e9e);
      text-decoration: line-through;
    }
    .price-off {
      font-size: 0.72rem;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 999px;
      background: rgba(244, 67, 54, 0.16);
      color: var(--error-color, #f44336);
    }
    /* Per-store availability line */
    /* JYSK size picker chips */
    .sizes {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 0.8rem;
    }
    .sizes__label {
      color: var(--secondary-text-color, #9e9e9e);
      flex: 0 0 auto;
    }
    .sizes__chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .sizes__chip {
      font: inherit;
      padding: 3px 10px;
      border-radius: 999px;
      border: 1px solid var(--divider-color, #e0e0e0);
      background: transparent;
      color: var(--primary-text-color, #212121);
      cursor: pointer;
      transition: border-color 0.12s ease, background 0.12s ease;
    }
    .sizes__chip:hover {
      border-color: var(--primary-color, #03a9f4);
      background: var(--secondary-background-color, #f5f5f5);
    }
    .sizes__chip--on {
      cursor: default;
      border-color: var(--primary-color, #03a9f4);
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      font-weight: 600;
    }

    /* Collapsible per-store availability (Húsa / JYSK) */
    .stores-d {
      font-size: 0.8rem;
      margin-top: 4px;
      min-width: 0;
    }
    .stores-d__summary {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      list-style: none;
      user-select: none;
    }
    .stores-d__summary::-webkit-details-marker {
      display: none;
    }
    .stores-d__summary ha-icon {
      --mdc-icon-size: 18px;
      flex: 0 0 auto;
    }
    .stores-d__label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    /* disclosure chevron, pushed to the right; flips when open */
    .stores-d__summary::after {
      content: "";
      flex: 0 0 auto;
      margin-left: auto;
      width: 0;
      height: 0;
      border-left: 4px solid transparent;
      border-right: 4px solid transparent;
      border-top: 5px solid currentColor;
      opacity: 0.55;
      transition: transform 0.15s ease;
    }
    .stores-d[open] .stores-d__summary::after {
      transform: rotate(180deg);
    }
    .stores-d--in .stores-d__summary {
      color: var(--success-color, #4caf50);
    }
    .stores-d--out .stores-d__summary {
      color: var(--error-color, #f44336);
    }
    .stores-d__list {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 10px;
      margin: 6px 0 0 24px;
      color: var(--primary-text-color);
    }
    .stores-d__store {
      white-space: nowrap;
    }
    .stores-d__store--out {
      color: var(--secondary-text-color, #9e9e9e);
      text-decoration: line-through;
    }
    .stores-d__star {
      color: #d91a00;
      font-weight: bold;
      margin-left: 1px;
    }
    .stores-d__hint {
      margin: 4px 0 0 24px;
      font-size: 0.72rem;
      color: var(--secondary-text-color, #9e9e9e);
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
      display: flex;
      align-items: center;
      gap: 4px;
      margin: 0;
      padding: 0;
    }
    .alts__link {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 6px 8px;
      border-radius: 6px;
      text-decoration: none;
      color: inherit;
      transition: background 120ms ease;
    }
    .alts__add {
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
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .alts__add:hover {
      color: var(--success-color, #2e7d32);
      background: rgba(46, 125, 50, 0.08);
      border-color: rgba(46, 125, 50, 0.25);
    }
    .alts__add:focus-visible {
      outline: 2px solid var(--success-color, #2e7d32);
      outline-offset: 1px;
    }
    .alts__add--done {
      cursor: default;
      color: var(--success-color, #2e7d32);
    }
    .alts__add--done:hover {
      background: transparent;
      border-color: transparent;
    }
    /* "Exclude site" button — red accent, mirrors .alts__add layout */
    .alts__exclude {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      font-size: 15px;
      line-height: 1;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .alts__exclude:hover {
      color: var(--error-color, #c62828);
      background: rgba(198, 40, 40, 0.08);
      border-color: rgba(198, 40, 40, 0.25);
    }
    .alts__exclude:focus-visible {
      outline: 2px solid var(--error-color, #c62828);
      outline-offset: 1px;
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
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      max-width: 100%;
    }
    .listings__retailer-name {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      min-width: 0;
    }
    .listings__badge {
      flex: 0 0 auto;
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 1px 6px;
      border-radius: 999px;
      white-space: nowrap;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
    }
    .listings__badge--noship {
      background: rgba(244, 67, 54, 0.16);
      color: var(--error-color, #f44336);
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
    .listings__actions {
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      gap: 2px;
    }
    .listings__edit {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      font-size: 14px;
      line-height: 1;
      cursor: pointer;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .listings__edit:hover {
      color: var(--primary-color, #1976d2);
      background: rgba(25, 118, 210, 0.08);
      border-color: rgba(25, 118, 210, 0.2);
    }
    .listings__edit:focus-visible {
      outline: 2px solid var(--primary-color, #1976d2);
      outline-offset: 1px;
    }
  `,e([pe({attribute:!1})],$e.prototype,"product",void 0),e([pe({attribute:!1})],$e.prototype,"onOpen",void 0),e([pe({attribute:!1})],$e.prototype,"onRefreshAlternatives",void 0),e([pe({type:Boolean,attribute:!1})],$e.prototype,"refreshingAlternatives",void 0),e([pe({type:Boolean,attribute:!1})],$e.prototype,"hideNonShipping",void 0),e([pe({attribute:!1})],$e.prototype,"onRemoveListing",void 0),e([pe({attribute:!1})],$e.prototype,"onAddListing",void 0),e([pe({attribute:!1})],$e.prototype,"onExcludeAlternative",void 0),e([pe({attribute:!1})],$e.prototype,"excludedAltHosts",void 0),e([pe({attribute:!1})],$e.prototype,"onEditListing",void 0),e([pe({attribute:!1})],$e.prototype,"onEditVariant",void 0),e([pe({attribute:!1})],$e.prototype,"onRefreshNow",void 0),e([pe({type:Boolean,attribute:!1})],$e.prototype,"refreshingNow",void 0),e([pe({attribute:!1})],$e.prototype,"onSetTarget",void 0),e([pe({attribute:!1})],$e.prototype,"onSetPaused",void 0),e([pe({attribute:!1})],$e.prototype,"onAlert",void 0),e([pe({attribute:!1})],$e.prototype,"onChangeSize",void 0),customElements.get("price-watch-card")||customElements.define("price-watch-card",$e);const we=["name","drop","cheapest","last_checked","below_target"],Se={name:"Name (A–Z)",drop:"Biggest drop",cheapest:"Cheapest",last_checked:"Last checked",below_target:"Below target"},Ee={anthropic_native:"AI web search",ai_synthesizer:"AI + web search",duckduckgo:"Web results (no AI)",none:""},Ae={none:"Free — web search, no AI",anthropic:"Anthropic (Claude)",openai_compatible:"OpenAI-compatible (Ollama, OpenAI, …)"},Pe={back_in_stock:"price_watch_back_in_stock",below_target:"price_watch_target_hit",price_drop:"price_watch_price_drop"};class PriceWatchPanel extends ne{constructor(){super(),this._products=[],this._registry=null,this._registryError=null,this._connected=!1,this._refreshingEntries=new Set,this._hideNonShipping=!1,this._search="",this._sort="name",this._hideDiscontinued=!1,this._refreshingNow=new Set,this._searchOpen=!1,this._searchQuery="",this._searchLoading=!1,this._searchResults=[],this._searchEngine="none",this._searchRan=!1,this._searchError=null,this._excludingHosts=new Set,this._hiddenAltHosts=new Set,this._hideNonShops=!1,this._trackTarget=null,this._trackName="",this._trackUrl="",this._trackTargetPrice="",this._tracking=!1,this._trackError=null,this._providerOpen=!1,this._providerLoading=!1,this._providerSaving=!1,this._providerError=null,this._providerSuccess=!1,this._providerAdvancedOpen=!1,this._pProvider="none",this._pApiKey="",this._pModel="",this._pBaseUrl="",this._pInputCost="",this._pOutputCost="",this._pMaxHtml="",this._pForceJson=!1,this._pExtraHeaders="",this._pExcludedDomains="",this._providerHasKey=!1,this._providerModels=[],this._selectorOpen=!1,this._selProduct=null,this._selListing=null,this._selPriceSelector="",this._selTitleSelector="",this._selCookies="",this._selTesting=!1,this._selTestResult=null,this._selTestError=null,this._selSaving=!1,this._selSaveError=null,this._selSaved=!1,this._selBookmarkletOpen=!1,this._variantOpen=!1,this._varProduct=null,this._varListing=null,this._varLoading=!1,this._varError=null,this._varGroups=null,this._varCombos=[],this._varSelection=[],this._varSupported=!0,this._varSaving=!1,this._varSaveError=null,this._varSaved=!1,this._alertOpen=!1,this._alertProduct=null,this._alertTrigger="back_in_stock",this._alertTargets=[],this._alertSelected=new Set,this._alertLoading=!1,this._alertSaving=!1,this._alertError=null,this._alertSaved=null,this._conn=null,this._states={},this._handleOpen=e=>{e.url&&window.open(e.url,"_blank","noopener,noreferrer")},this._handleRefreshAlternatives=async e=>{if(this._conn&&!this._refreshingEntries.has(e.entryId)){this._refreshingEntries=new Set([...this._refreshingEntries,e.entryId]);try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"find_alternatives",service_data:{entry_id:e.entryId}})}catch(e){console.error("[price-watch-panel] find_alternatives failed:",e)}finally{const t=new Set(this._refreshingEntries);t.delete(e.entryId),this._refreshingEntries=t}}},this._handleRemoveListing=async(e,t)=>{if(this._conn)if(t.isPrimary)console.warn("[price-watch-panel] refusing to remove primary listing",t.listingId);else try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"remove_listing",service_data:{entry_id:e.entryId,listing_id:t.listingId}})}catch(e){console.error("[price-watch-panel] remove_listing failed:",e)}},this._handleAddListing=async(e,t)=>{if(!this._conn)return;const r=(t.url??"").trim();if(!r)return;const i={entry_id:e.entryId,url:r};t.retailer&&(i.retailer=t.retailer),t.currency&&(i.currency=t.currency);try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"add_listing",service_data:i})}catch(e){console.error("[price-watch-panel] add_listing failed:",e)}},this._handleEditListing=(e,t)=>{this._selProduct=e,this._selListing=t,this._selPriceSelector="",this._selTitleSelector="",this._selCookies="",this._selTestResult=null,this._selTestError=null,this._selSaveError=null,this._selSaved=!1,this._selBookmarkletOpen=!1,this._selectorOpen=!0},this._closeSelectorEditor=()=>{this._selectorOpen=!1,this._selProduct=null,this._selListing=null},this._onSelectorBackdropClick=e=>{e.target===e.currentTarget&&this._closeSelectorEditor()},this._onSelPriceInput=e=>{this._selPriceSelector=e.target.value},this._onSelTitleInput=e=>{this._selTitleSelector=e.target.value},this._onSelCookiesInput=e=>{this._selCookies=e.target.value},this._runSelectorTest=async()=>{if(!this._conn||!this._selListing)return;const e=(this._selListing.url??"").trim(),t=this._selPriceSelector.trim();if(!e)return void(this._selTestError="This listing has no URL to test against.");if(!t)return void(this._selTestError="Enter a price selector first.");this._selTesting=!0,this._selTestError=null,this._selTestResult=null;const r=this._selTitleSelector.trim()||"h1",i=this._selCookies.trim();try{const s=await this._conn.sendMessagePromise({type:"price_watch/test_selector",url:e,price_selector:t,title_selector:r,...i?{request_cookies:i}:{}});this._selTestResult=s}catch(e){this._selTestError=e?.message??"Test failed."}finally{this._selTesting=!1}},this._saveSelector=async()=>{if(!this._conn||!this._selProduct||!this._selListing)return;const e=this._selPriceSelector.trim(),t=this._selCookies.trim();if(!e&&!t)return void(this._selSaveError="Enter a price selector or cookies first.");const r={entry_id:this._selProduct.entryId,listing_id:this._selListing.listingId};if(e){const t=this._selTitleSelector.trim()||"h1";r.custom_parser={type:"css",selectors:{price:e,title:t},transforms:{price:"price_clean"}}}t&&(r.request_cookies=t),this._selSaving=!0,this._selSaveError=null,this._selSaved=!1;try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"edit_listing",service_data:r}),this._selSaved=!0,window.setTimeout(()=>this._closeSelectorEditor(),1200)}catch(e){this._selSaveError=e?.message??"Save failed."}finally{this._selSaving=!1}},this._clearSelector=async()=>{if(this._conn&&this._selProduct&&this._selListing&&window.confirm("Remove the custom price selector and any stored cookies, and go back to automatic extraction?")){this._selSaving=!0,this._selSaveError=null;try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"edit_listing",service_data:{entry_id:this._selProduct.entryId,listing_id:this._selListing.listingId,custom_parser:"",request_cookies:""}}),this._selSaved=!0,window.setTimeout(()=>this._closeSelectorEditor(),1200)}catch(e){this._selSaveError=e?.message??"Clear failed."}finally{this._selSaving=!1}}},this._handleEditVariant=(e,t)=>{this._varProduct=e,this._varListing=t,this._varError=null,this._varGroups=null,this._varCombos=[],this._varSelection=[],this._varSupported=!0,this._varSaveError=null,this._varSaved=!1,this._variantOpen=!0,this._loadVariants()},this._closeVariantPicker=()=>{this._variantOpen=!1,this._varProduct=null,this._varListing=null,this._varGroups=null,this._varCombos=[],this._varSelection=[]},this._handleChangeSize=async(e,t,r)=>{if(!this._conn)return;const i=e.listings.find(e=>e.isPrimary),s=i?.listingId;if(s){if(window.confirm(`Track the ${r} size instead?\n\nThis product will follow that size's own page — its price, stock and discount.`))try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"edit_listing",service_data:{entry_id:e.entryId,listing_id:s,url:t}})}catch(e){window.alert(`Could not switch size: ${e?.message??"unknown error"}`)}}else window.alert("Could not resolve the primary listing to switch size.")},this._onVariantBackdropClick=e=>{e.target===e.currentTarget&&this._closeVariantPicker()},this._loadVariants=async()=>{if(this._conn&&this._varProduct&&this._varListing){this._varLoading=!0,this._varError=null;try{const e={type:"price_watch/list_variants",entry_id:this._varProduct.entryId};this._varListing.isPrimary||(e.listing_id=this._varListing.listingId);const t=await this._conn.sendMessagePromise(e);if(this._varSupported=!!t.supported,!t.supported)return this._varGroups=null,this._varCombos=[],void(this._varSelection=[]);const r=t.options??[];this._varGroups=r,this._varCombos=t.variants??[];const i=(t.current??[]).map(e=>e.toLowerCase());this._varSelection=r.map(e=>{const t=e.choices.find(e=>i.includes(e.toLowerCase()));return t??""})}catch(e){this._varError=e?.message??"Could not read variants."}finally{this._varLoading=!1}}},this._onVariantSelect=(e,t)=>{const r=[...this._varSelection];r[e]=t,this._varSelection=r},this._saveVariant=async()=>{if(!this._conn||!this._varProduct||!this._varListing)return;const e=this._varSelection.filter(e=>!!e);if(0!==e.length){this._varSaving=!0,this._varSaveError=null,this._varSaved=!1;try{const t=this._varListing.isPrimary?{type:"call_service",domain:"price_watch",service:"set_variant",service_data:{entry_id:this._varProduct.entryId,variant_options:e}}:{type:"call_service",domain:"price_watch",service:"edit_listing",service_data:{entry_id:this._varProduct.entryId,listing_id:this._varListing.listingId,variant_options:e}};await this._conn.sendMessagePromise(t),this._varSaved=!0,window.setTimeout(()=>this._closeVariantPicker(),1200)}catch(e){this._varSaveError=e?.message??"Save failed."}finally{this._varSaving=!1}}else this._varSaveError="Pick an option in each group first."},this._clearVariant=async()=>{if(this._conn&&this._varProduct&&this._varListing&&window.confirm("Stop following a specific variant and go back to the default price?")){this._varSaving=!0,this._varSaveError=null;try{const e=this._varListing.isPrimary?{type:"call_service",domain:"price_watch",service:"set_variant",service_data:{entry_id:this._varProduct.entryId,variant_options:[]}}:{type:"call_service",domain:"price_watch",service:"edit_listing",service_data:{entry_id:this._varProduct.entryId,listing_id:this._varListing.listingId,variant_options:[]}};await this._conn.sendMessagePromise(e),this._varSaved=!0,window.setTimeout(()=>this._closeVariantPicker(),1200)}catch(e){this._varSaveError=e?.message??"Clear failed."}finally{this._varSaving=!1}}},this._copyBookmarklet=async()=>{const e=this._bookmarkletHref();try{await navigator.clipboard.writeText(e)}catch{this._selBookmarkletOpen=!0}},this._handleToggleHideNonShipping=()=>{this._hideNonShipping=!this._hideNonShipping;try{localStorage.setItem(PriceWatchPanel.HIDE_NONSHIP_KEY,this._hideNonShipping?"1":"0")}catch{}},this._handleToggleHideDiscontinued=()=>{this._hideDiscontinued=!this._hideDiscontinued;try{localStorage.setItem(PriceWatchPanel.HIDE_DISCONTINUED_KEY,this._hideDiscontinued?"1":"0")}catch{}},this._handleSearch=e=>{this._search=e.target.value},this._handleSort=e=>{const t=e.target.value;this._sort=t;try{localStorage.setItem(PriceWatchPanel.SORT_KEY,t)}catch{}},this._handleRefreshNow=async e=>{if(this._conn&&!this._refreshingNow.has(e.entryId)){this._refreshingNow=new Set([...this._refreshingNow,e.entryId]);try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"refresh_now",service_data:{entry_id:e.entryId}})}catch(e){console.error("[price-watch-panel] refresh_now failed:",e)}finally{const t=new Set(this._refreshingNow);t.delete(e.entryId),this._refreshingNow=t}}},this._handleSetTarget=async(e,t)=>{if(this._conn)try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"set_target",service_data:null===t?{entry_id:e.entryId}:{entry_id:e.entryId,target_price:t}})}catch(e){console.error("[price-watch-panel] set_target failed:",e)}},this._handleSetPaused=async(e,t)=>{if(this._conn)try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"set_paused",service_data:{entry_id:e.entryId,paused:t}})}catch(e){console.error("[price-watch-panel] set_paused failed:",e)}},this._handleAddProduct=()=>{window.history.pushState(null,"","/config/integrations/dashboard/add?domain=price_watch"),window.dispatchEvent(new CustomEvent("location-changed"))},this._openSearch=()=>{this._searchOpen=!0,this._trackTarget=null,this._trackError=null},this._closeSearch=()=>{this._searchOpen=!1,this._trackTarget=null,this._searchError=null,this._trackError=null},this._onBackdropClick=e=>{e.target===e.currentTarget&&this._closeSearch()},this._handleSearchQueryInput=e=>{this._searchQuery=e.target.value},this._handleSearchKeydown=e=>{"Enter"===e.key?(e.preventDefault(),this._runSearch()):"Escape"===e.key&&this._closeSearch()},this._runSearch=async()=>{if(!this._conn)return;const e=this._searchQuery.trim();if(e&&!this._searchLoading){this._searchLoading=!0,this._searchError=null,this._trackTarget=null;try{const t=await this._conn.sendMessagePromise({type:"price_watch/search",query:e,max_results:8});this._searchResults=t.results??[],this._searchEngine=t.engine??"none",this._searchRan=!0}catch(e){const t=String(e&&"object"==typeof e&&"message"in e?e.message:e);this._searchError=t||"Search failed.",this._searchResults=[],this._searchRan=!0,console.error("[price-watch-panel] search failed:",e)}finally{this._searchLoading=!1}}},this._pickResult=e=>{this._trackTarget=e,this._trackName=e.title,this._trackUrl=e.url,this._trackTargetPrice="",this._trackError=null},this._cancelTrack=()=>{this._trackTarget=null,this._trackError=null},this._handleTrackNameInput=e=>{this._trackName=e.target.value},this._handleTrackUrlInput=e=>{this._trackUrl=e.target.value},this._handleTrackTargetInput=e=>{this._trackTargetPrice=e.target.value},this._confirmTrack=async()=>{if(!this._conn||this._tracking)return;const e=this._trackUrl.trim();if(!e)return void(this._trackError="A URL is required to track a product.");const t=this._trackName.trim(),r=this._trackTargetPrice.trim();let i=null;if(""!==r){const e=Number(r);if(Number.isNaN(e))return void(this._trackError="Target price must be a number.");i=e}this._tracking=!0,this._trackError=null;try{await this._conn.sendMessagePromise({type:"call_service",domain:"price_watch",service:"track_product",service_data:{url:e,...t?{name:t}:{},...null!==i?{target_price:i}:{}}}),this._closeSearch()}catch(e){const t=String(e&&"object"==typeof e&&"message"in e?e.message:e);this._trackError=t||"Could not add product.",console.error("[price-watch-panel] track_product failed:",e)}finally{this._tracking=!1}},this._openProviderEditor=async()=>{if(this._providerOpen=!0,this._providerError=null,this._providerSuccess=!1,this._providerAdvancedOpen=!1,this._conn){this._providerLoading=!0;try{const e=await this._conn.sendMessagePromise({type:"price_watch/get_provider_settings"});this._applyProviderSettings(e)}catch(e){this._providerError=this._wsErrorMessage(e)||"Could not load provider settings.",console.error("[price-watch-panel] get_provider_settings failed:",e)}finally{this._providerLoading=!1}}else this._providerError="Not connected to Home Assistant yet."},this._closeProviderEditor=()=>{this._providerOpen=!1,this._providerError=null,this._providerSuccess=!1},this._onProviderBackdropClick=e=>{e.target===e.currentTarget&&this._closeProviderEditor()},this._onProviderChange=e=>{this._pProvider=e.target.value,this._providerSuccess=!1,this._providerError=null},this._saveProvider=async()=>{if(!this._conn||this._providerSaving)return;this._providerSaving=!0,this._providerError=null,this._providerSuccess=!1;const e={provider:this._pProvider},t=this._pApiKey.trim();if(t&&(e.api_key=t),"anthropic"===this._pProvider)e.model=this._pModel;else if("openai_compatible"===this._pProvider){e.base_url=this._pBaseUrl.trim(),e.model=this._pModel.trim(),e.input_cost_per_mtok=Number(this._pInputCost)||0,e.output_cost_per_mtok=Number(this._pOutputCost)||0,e.max_html_chars=Number(this._pMaxHtml)||1e5,e.force_json_mode=this._pForceJson;const t=this._pExtraHeaders.trim();t&&(e.extra_headers=t)}e.excluded_domains=this._pExcludedDomains;try{const t=await this._conn.sendMessagePromise({type:"price_watch/set_provider_settings",...e});this._applyProviderSettings(t),this._providerSuccess=!0}catch(e){this._providerError=this._wsErrorMessage(e)||"Could not save provider settings.",console.error("[price-watch-panel] set_provider_settings failed:",e)}finally{this._providerSaving=!1}},this._handleAlert=e=>{this._alertProduct=e,this._alertTrigger="back_in_stock",this._alertSelected=new Set,this._alertError=null,this._alertSaved=null,this._alertOpen=!0,this._loadNotifyTargets()},this._closeAlert=()=>{this._alertOpen=!1,this._alertProduct=null},this._onAlertBackdropClick=e=>{e.target===e.currentTarget&&this._closeAlert()},this._loadNotifyTargets=async()=>{if(this._conn){this._alertLoading=!0,this._alertError=null;try{const e=await this._conn.sendMessagePromise({type:"price_watch/list_notify_targets"});this._alertTargets=e.targets??[]}catch(e){this._alertError=e?.message??"Could not load notify targets."}finally{this._alertLoading=!1}}},this._setAlertTrigger=e=>{this._alertTrigger=e},this._toggleAlertTarget=e=>{const t=new Set(this._alertSelected);t.has(e)?t.delete(e):t.add(e),this._alertSelected=t},this._createAlert=async()=>{const e=this._alertProduct;if(!e)return;const t=[...this._alertSelected];if(0===t.length)return void(this._alertError="Pick at least one device to notify.");const r=this._alertTrigger,i=Pe[r],s={back_in_stock:{emoji:"🛒",title:"Back in stock!",body:"{{ trigger.event.data.title }} is back in stock at {{ trigger.event.data.price }} {{ trigger.event.data.currency }}"},below_target:{emoji:"🎯",title:"Target price hit!",body:"{{ trigger.event.data.title }} hit your target — now {{ trigger.event.data.price }} {{ trigger.event.data.currency }}"},price_drop:{emoji:"📉",title:"Price drop",body:"{{ trigger.event.data.title }}: {{ trigger.event.data.price }} {{ trigger.event.data.currency }} (was {{ trigger.event.data.previous_price }})"}}[r],o=t.map(e=>({service:e,data:{title:`${s.emoji} ${s.title}`,message:s.body,data:{url:"{{ trigger.event.data.url }}"}}})),a={alias:`Price Watch: ${e.title} — ${s.title}`,description:"Created via the Price Watch panel's Alert-me button.",mode:"single",trigger:[{platform:"event",event_type:i,event_data:{entry_id:e.entryId}}],action:o},n=`pw_alert_${e.entryId.toLowerCase()}_${r}`;this._alertSaving=!0,this._alertError=null,this._alertSaved=null;try{await this._createAutomation(n,a),this._alertSaved=a.alias,window.setTimeout(()=>this._closeAlert(),1600)}catch(e){this._alertError=e?.message??"Could not create the alert."}finally{this._alertSaving=!1}},this._openIntegrationSettings=()=>{window.history.pushState(null,"","/config/integrations/integration/price_watch"),window.dispatchEvent(new CustomEvent("location-changed",{detail:{replace:!1}}))},this._handleHideNonShopsToggle=e=>{this._hideNonShops=e.target.checked;try{localStorage.setItem(PriceWatchPanel.HIDE_NONSHOPS_KEY,this._hideNonShops?"1":"0")}catch{}},this._excludeResultSite=async e=>{if(!this._conn)return;const t=this._hostOf(e.url);if(t){this._excludingHosts=new Set(this._excludingHosts).add(t);try{await this._conn.sendMessagePromise({type:"price_watch/exclude_domain",domain:t}),this._searchResults=this._searchResults.filter(e=>this._hostOf(e.url)!==t)}catch(e){this._searchError=e?.message??`Could not exclude ${t}.`}finally{const e=new Set(this._excludingHosts);e.delete(t),this._excludingHosts=e}}},this._handleExcludeAlternative=async(e,t)=>{if(!this._conn)return;const r=this._hostOf(t.url??"");if(r)try{await this._conn.sendMessagePromise({type:"price_watch/exclude_domain",domain:r}),this._hiddenAltHosts=new Set(this._hiddenAltHosts).add(r)}catch(e){window.alert(`Could not exclude ${r}: ${e?.message??"unknown error"}`)}};try{this._hideNonShipping="1"===localStorage.getItem(PriceWatchPanel.HIDE_NONSHIP_KEY),this._hideDiscontinued="1"===localStorage.getItem(PriceWatchPanel.HIDE_DISCONTINUED_KEY),this._hideNonShops="1"===localStorage.getItem(PriceWatchPanel.HIDE_NONSHOPS_KEY);const e=localStorage.getItem(PriceWatchPanel.SORT_KEY);e&&we.includes(e)&&(this._sort=e)}catch{}}connectedCallback(){super.connectedCallback(),this._bootstrap()}disconnectedCallback(){super.disconnectedCallback(),this._unsubState?.(),this._unsubRegistry?.(),this._unsubState=void 0,this._unsubRegistry=void 0}async _bootstrap(){const e=window.hassConnection;if(!e)return void(this._registryError="Home Assistant WebSocket connection not available on this page. Try reloading.");let t;try{const r=await e;t=r.conn,this._conn=t,this._connected=!0}catch(e){const t=e instanceof Error?e.message:String(e);return void(this._registryError=`Could not open HA connection: ${t}`)}try{await this._fetchRegistry(t),await this._fetchInitialStates(t),this._unsubState=await t.subscribeEvents(e=>this._onStateChanged(e),"state_changed"),this._unsubRegistry=await t.subscribeEvents(()=>{this._fetchRegistry(t).then(()=>this._fetchInitialStates(t))},"entity_registry_updated")}catch(e){const t=e instanceof Error?e.message:String(e);this._registryError=`Setup failed after connection: ${t}`,console.error("[price-watch-panel]",e)}}async _fetchRegistry(e){const t=await e.sendMessagePromise({type:"config/entity_registry/list"}),r=new Map;for(const e of t)"price_watch"===e.platform&&r.set(e.unique_id,e.entity_id);this._registry={byUniqueId:r},this._registryError=null,this._rebuildProducts()}async _fetchInitialStates(e){if(!this._registry)return;const t=new Set(this._registry.byUniqueId.values()),r=await e.sendMessagePromise({type:"get_states"}),i={};for(const e of r)t.has(e.entity_id)&&(i[e.entity_id]=e);this._states=i,this._rebuildProducts()}_onStateChanged(e){const{entity_id:t,new_state:r}=e.data;if(!this._registry)return;new Set(this._registry.byUniqueId.values()).has(t)&&(null===r?delete this._states[t]:this._states={...this._states,[t]:r},this._rebuildProducts())}_rebuildProducts(){if(!this._registry)return void(this._products=[]);const e={states:this._states};this._products=function(e,t){const r=new Map;for(const[e,i]of t.byUniqueId){const t=ye(e);if(!t)continue;let s=r.get(t.entryId);if(s||(s={legacy:new Map,listings:new Map},r.set(t.entryId,s)),null===t.listingId)s.legacy.set(t.key,i);else{let e=s.listings.get(t.listingId);e||(e=new Map,s.listings.set(t.listingId,e)),e.set(t.key,i)}}const i=[];for(const[t,s]of r){const r=s.legacy,o=r.get("price");if(!o)continue;const a=e.states[o];if(!a)continue;const n=a.attributes,l={entryId:t,title:String(n.title??n.friendly_name??"Unknown product"),url:String(n.product_url??""),retailer:"string"==typeof n.retailer?n.retailer:null,imageUrl:"string"==typeof n.image_url?n.image_url:null,imageProxyUrl:null,imageBroken:!1,price:_e(a.state),currency:"string"==typeof n.unit_of_measurement?n.unit_of_measurement:"string"==typeof n.currency?n.currency:"",priceLocal:null,localCurrency:null,lowest:null,highest:null,targetDiff:null,targetPrice:"number"==typeof n.target_price?n.target_price:null,onSale:!0===n.on_sale,originalPrice:"number"==typeof n.original_price?n.original_price:null,discountPercent:"number"==typeof n.discount_percent?n.discount_percent:null,storeAvailability:Array.isArray(n.store_availability)?n.store_availability.map(e=>({store:e.store,status:e.status,fromWarehouse:!0===e.from_warehouse})):null,availableStores:Array.isArray(n.available_stores)?n.available_stores:null,stockFromWarehouse:!0===n.stock_from_warehouse,sizeOptions:Array.isArray(n.size_options)?n.size_options:null,paused:!0===n.paused,inStock:null,stockCount:"number"==typeof n.stock_count?n.stock_count:null,discontinued:!0===n.discontinued,discontinuedReason:"string"==typeof n.discontinued_reason?n.discontinued_reason:null,discontinuedAt:"string"==typeof n.discontinued_at?n.discontinued_at:null,lastKnownPrice:"number"==typeof n.last_known_price?n.last_known_price:null,lastKnownCurrency:"string"==typeof n.last_known_currency?n.last_known_currency:null,lastCheck:"string"==typeof n.last_check?n.last_check:null,history:fe(n.price_history),alternatives:me(n.alternatives),alternativesFetchedAt:"string"==typeof n.alternatives_fetched_at?n.alternatives_fetched_at:null,alternativesError:"string"==typeof n.alternatives_error&&n.alternatives_error?n.alternatives_error:null,entityIds:{price:o},listings:[]},c=[["price_local",e=>{l.priceLocal=_e(e.state),l.localCurrency="string"==typeof e.attributes.unit_of_measurement?e.attributes.unit_of_measurement:null,l.entityIds.priceLocal=e.entity_id}],["lowest",e=>{l.lowest=_e(e.state),l.entityIds.lowest=e.entity_id}],["highest",e=>{l.highest=_e(e.state),l.entityIds.highest=e.entity_id}],["target_diff",e=>{l.targetDiff=_e(e.state),l.entityIds.targetDiff=e.entity_id}],["stock_count",e=>{l.stockCount=_e(e.state),l.entityIds.stockCount=e.entity_id}],["in_stock",e=>{l.inStock=ue(e.state),l.entityIds.inStock=e.entity_id}],["discontinued",e=>{const t=ue(e.state);null!=t&&(l.discontinued=t),l.entityIds.discontinued=e.entity_id}],["photo",e=>{if("unavailable"===e.state||"unknown"===e.state)return void(l.imageBroken=!0);const t=e.attributes.entity_picture;"string"==typeof t&&t.length>0&&(l.imageProxyUrl=t)}]];for(const[t,i]of c){const s=r.get(t);if(!s)continue;const o=e.states[s];o&&i(o)}const d="string"==typeof n.listing_id&&n.listing_id?n.listing_id:`l_${t.slice(-12).toLowerCase()}`,p=be(e,s.legacy,d,!0);p&&l.listings.push(p);for(const[t,r]of s.listings){const i=be(e,r,t,!1);i&&l.listings.push(i)}i.push(l)}return i.sort((e,t)=>e.discontinued!==t.discontinued?e.discontinued?1:-1:e.title.localeCompare(t.title)),i}(e,this._registry)}_matchedCombo(){if(!this._varGroups||0===this._varGroups.length)return null;if(this._varSelection.some(e=>!e))return null;const e=this._varSelection.map(e=>e.toLowerCase());return this._varCombos.find(t=>{const r=t.labels.map(e=>e.toLowerCase());return e.every(e=>r.includes(e))})??null}_bookmarkletHref(){return"javascript:"+encodeURIComponent("(function(){\n  if(window.__pwPickerActive){return;}\n  window.__pwPickerActive=true;\n  var hl=document.createElement('div');\n  hl.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:rgba(25,118,210,0.25);border:2px solid #1976d2;border-radius:3px;transition:all 40ms ease';\n  var tip=document.createElement('div');\n  tip.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:#1976d2;color:#fff;font:12px/1.4 sans-serif;padding:3px 6px;border-radius:4px;max-width:90vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis';\n  document.body.appendChild(hl);document.body.appendChild(tip);\n  function sel(el){\n    if(!el||el.nodeType!==1)return'';\n    if(el.id&&/^[A-Za-z][-_A-Za-z0-9]*$/.test(el.id))return'#'+el.id;\n    var parts=[],node=el,depth=0;\n    while(node&&node.nodeType===1&&depth<5){\n      var part=node.tagName.toLowerCase();\n      if(node.id&&/^[A-Za-z][-_A-Za-z0-9]*$/.test(node.id)){parts.unshift('#'+node.id);break;}\n      var cls=(node.getAttribute('class')||'').trim().split(/\\s+/).filter(function(c){return c&&!/^(is-|has-|js-)/.test(c)&&c.length<30;}).slice(0,2);\n      if(cls.length)part+='.'+cls.join('.');\n      var p=node.parentElement;\n      if(p){var sib=Array.prototype.filter.call(p.children,function(c){return c.tagName===node.tagName;});if(sib.length>1){part+=':nth-of-type('+(sib.indexOf(node)+1)+')';}}\n      parts.unshift(part);node=p;depth++;\n    }\n    return parts.join(' > ');\n  }\n  function move(e){\n    var el=e.target;if(!el||el===hl||el===tip)return;\n    var r=el.getBoundingClientRect();\n    hl.style.left=r.left+'px';hl.style.top=r.top+'px';hl.style.width=r.width+'px';hl.style.height=r.height+'px';\n    var s=sel(el);tip.textContent=s;\n    tip.style.left=r.left+'px';tip.style.top=(r.top>24?r.top-24:r.bottom+4)+'px';\n  }\n  function done(){window.removeEventListener('mousemove',move,true);window.removeEventListener('click',click,true);window.removeEventListener('keydown',key,true);hl.remove();tip.remove();window.__pwPickerActive=false;}\n  function click(e){\n    e.preventDefault();e.stopPropagation();\n    var s=sel(e.target);\n    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(s).then(function(){},function(){window.prompt('Copy this selector:',s);});}\n    else{window.prompt('Copy this selector:',s);}\n    done();\n  }\n  function key(e){if(e.key==='Escape'){done();}}\n  window.addEventListener('mousemove',move,true);\n  window.addEventListener('click',click,true);\n  window.addEventListener('keydown',key,true);\n})();")}_visibleProducts(){const e=this._search.trim().toLowerCase();let t=this._products.filter(t=>{if(this._hideDiscontinued&&t.discontinued)return!1;if(!e)return!0;return`${t.title} ${t.retailer??""}`.toLowerCase().includes(e)});const r=(e,t)=>e.title.localeCompare(t.title),i=e=>null===e?Number.POSITIVE_INFINITY:e;return t=[...t].sort((e,t)=>{switch(this._sort){case"cheapest":return i(e.price)-i(t.price)||r(e,t);case"last_checked":{const i=e.lastCheck?Date.parse(e.lastCheck):-1/0;return(t.lastCheck?Date.parse(t.lastCheck):-1/0)-i||r(e,t)}case"drop":{const i=null!==e.highest&&null!==e.price?e.highest-e.price:-1;return(null!==t.highest&&null!==t.price?t.highest-t.price:-1)-i||r(e,t)}case"below_target":{const i=e=>null!==e.targetPrice&&null!==e.price&&e.price<=e.targetPrice?e.targetPrice-e.price:-1;return i(t)-i(e)||r(e,t)}default:return r(e,t)}}),t}_wsErrorMessage(e){return String(e&&"object"==typeof e&&"message"in e?e.message:e)}_applyProviderSettings(e){this._providerModels=e.anthropic_models??[],this._pProvider=e.provider,this._pModel=e.model||this._providerModels[0]||"",this._pBaseUrl=e.base_url??"",this._providerHasKey=!!e.has_api_key,this._pApiKey="",this._pInputCost=String(e.input_cost_per_mtok??0),this._pOutputCost=String(e.output_cost_per_mtok??0),this._pMaxHtml=String(e.max_html_chars??1e5),this._pForceJson=!!e.force_json_mode,this._pExtraHeaders=e.extra_headers??"",this._pExcludedDomains=(e.excluded_domains??[]).join("\n")}async _createAutomation(e,t){const r=await window.hassConnection,i=r?.auth,s=i?.accessToken??i?.data?.access_token,o=await fetch(`/api/config/automation/config/${encodeURIComponent(e)}`,{method:"POST",headers:{"Content-Type":"application/json",...s?{Authorization:`Bearer ${s}`}:{}},body:JSON.stringify(t)});if(!o.ok){const e=await o.text().catch(()=>"");throw new Error(`Home Assistant rejected the automation (HTTP ${o.status}). ${e.slice(0,180)}`)}}_renderHeader(){return F`
      <header class="panel-header">
        <div class="panel-header__title">
          <h1>Price Watch</h1>
        </div>
        <div class="panel-header__actions">
          <button
            class="add-button add-button--secondary"
            @click=${this._openIntegrationSettings}
            title="Open the Price Watch integration page in Home Assistant settings — region, currency, budgets, and tracked products"
          >
            🛠 Settings
          </button>
          <button
            class="add-button add-button--secondary"
            @click=${this._openProviderEditor}
            title="Choose AI provider (Free / Anthropic / OpenAI-compatible)"
          >
            ⚙ AI provider
          </button>
          <button
            class="add-button add-button--secondary"
            @click=${this._openSearch}
          >
            🔍 Search &amp; add
          </button>
          <button class="add-button" @click=${this._handleAddProduct}>
            + Add product
          </button>
        </div>
      </header>
    `}_renderSearchModal(){return this._searchOpen?F`
      <div
        class="modal-backdrop"
        @click=${this._onBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Search and add a product"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>${this._trackTarget?"Track this product":"Search & add"}</h2>
            <button
              class="modal__close"
              @click=${this._closeSearch}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          ${this._trackTarget?this._renderTrackForm():this._renderSearchBody()}
        </div>
      </div>
    `:null}_renderSearchBody(){return F`
      <div class="modal__searchbar">
        <input
          type="search"
          class="modal__searchinput"
          placeholder="Search for a product to track…"
          .value=${this._searchQuery}
          @input=${this._handleSearchQueryInput}
          @keydown=${this._handleSearchKeydown}
          aria-label="Product search query"
          autofocus
        />
        <button
          class="add-button"
          @click=${this._runSearch}
          ?disabled=${this._searchLoading||!this._searchQuery.trim()}
        >
          ${this._searchLoading?"Searching…":"Search"}
        </button>
      </div>
      ${this._renderSearchResults()}
    `}_renderSearchResults(){if(this._searchLoading)return F`<div class="modal__status">Searching the web…</div>`;if(this._searchError)return F`
        <div class="modal__status modal__status--error">
          ⚠ ${this._searchError}
        </div>
      `;if(!this._searchRan)return F`
        <div class="modal__status">
          Type what you're looking for and press Enter — e.g. a product
          name, model number, or brand.
        </div>
      `;if(0===this._searchResults.length)return F`
        <div class="modal__status">
          No results. Try a different or more specific query.
        </div>
      `;const e=this._searchResults.filter(e=>e.likely_non_shop).length,t=this._hideNonShops?this._searchResults.filter(e=>!e.likely_non_shop):this._searchResults;return F`
      <div class="results-bar">
        <div class="modal__engine">${Ee[this._searchEngine]}</div>
        ${e>0?F`<label
              class="results-bar__toggle"
              title="Hide GitHub, YouTube, wikis, forums and other non-store results"
            >
              <input
                type="checkbox"
                .checked=${this._hideNonShops}
                @change=${this._handleHideNonShopsToggle}
              />
              Hide non-stores (${e})
            </label>`:null}
      </div>
      ${0===t.length?F`<div class="modal__status">
            All ${this._searchResults.length} results were non-stores and are
            hidden. Untick "Hide non-stores" to see them.
          </div>`:F`<ul class="results">
            ${t.map(e=>this._renderResultRow(e))}
          </ul>`}
    `}_renderResultRow(e){const t=null!==e.price?`${e.price} ${e.currency}`.trim():"Price unknown",r=!0===e.ships_to_user_region?F`<span class="results__ship results__ship--yes">Ships to you</span>`:!1===e.ships_to_user_region?F`<span class="results__ship results__ship--no">Doesn't ship</span>`:null,i=e.likely_non_shop?F`<span class="results__kind results__kind--info"
          >not a store?</span
        >`:null;return F`
      <li class="results__row ${e.likely_non_shop?"results__row--muted":""}">
        <div class="results__thumb">
          ${e.image_url?F`<img src=${e.image_url} alt="" loading="lazy" />`:F`<span class="results__thumb-ph">🏷️</span>`}
        </div>
        <div class="results__info">
          <a
            class="results__title results__title--link"
            href=${e.url}
            target="_blank"
            rel="noopener noreferrer"
            title=${`${e.title} — open to verify`}
          >
            ${e.title}
            <span class="results__ext" aria-hidden="true">↗</span>
          </a>
          <div class="results__meta">
            <span class="results__price">${t}</span>
            ${e.retailer?F`<span class="results__retailer">${e.retailer}</span>`:null}
            ${i}
            ${r}
          </div>
          ${e.notes?F`<div class="results__notes">${e.notes}</div>`:null}
        </div>
        <div class="results__actions">
          <button class="results__add" @click=${()=>this._pickResult(e)}>
            Track
          </button>
          <button
            class="results__exclude"
            @click=${()=>this._excludeResultSite(e)}
            ?disabled=${this._excludingHosts.has(this._hostOf(e.url))}
            title=${`Hide ${this._hostOf(e.url)||"this site"} from all current and future searches`}
          >
            ${this._excludingHosts.has(this._hostOf(e.url))?"Excluding…":"Exclude site"}
          </button>
        </div>
      </li>
    `}_hostOf(e){try{return new URL(e).hostname.replace(/^www\./i,"").toLowerCase()}catch{return""}}_renderTrackForm(){const e=this._trackTarget;return F`
      <div class="trackform">
        ${e&&null!==e.price?F`<div class="trackform__hint">
              Currently ${e.price} ${e.currency} at
              ${e.retailer||"this retailer"}.
            </div>`:null}
        <label class="trackform__field">
          <span>Name</span>
          <input
            type="text"
            .value=${this._trackName}
            @input=${this._handleTrackNameInput}
            placeholder="Display name"
          />
        </label>
        <label class="trackform__field">
          <span>URL</span>
          <input
            type="url"
            .value=${this._trackUrl}
            @input=${this._handleTrackUrlInput}
            placeholder="https://…"
          />
        </label>
        <label class="trackform__field">
          <span>Target price <em>(optional)</em></span>
          <input
            type="number"
            step="any"
            .value=${this._trackTargetPrice}
            @input=${this._handleTrackTargetInput}
            placeholder="Alert when at or below…"
          />
        </label>
        ${this._trackError?F`<div class="modal__status modal__status--error">
              ⚠ ${this._trackError}
            </div>`:null}
        <div class="trackform__actions">
          <button class="trackform__cancel" @click=${this._cancelTrack}>
            Back
          </button>
          <button
            class="add-button"
            @click=${this._confirmTrack}
            ?disabled=${this._tracking||!this._trackUrl.trim()}
          >
            ${this._tracking?"Adding…":"Track product"}
          </button>
        </div>
      </div>
    `}_renderProviderModal(){return this._providerOpen?F`
      <div
        class="modal-backdrop"
        @click=${this._onProviderBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="AI provider settings"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>AI provider</h2>
            <button
              class="modal__close"
              @click=${this._closeProviderEditor}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          ${this._providerLoading?F`<div class="modal__status">Loading current settings…</div>`:this._renderProviderForm()}
        </div>
      </div>
    `:null}_renderProviderForm(){return F`
      <div class="trackform">
        <label class="trackform__field">
          <span>Provider</span>
          <select @change=${this._onProviderChange}>
            ${["none","anthropic","openai_compatible"].map(e=>F`
                <option value=${e} ?selected=${this._pProvider===e}>
                  ${Ae[e]}
                </option>
              `)}
          </select>
        </label>

        ${"none"===this._pProvider?this._renderNoneInfo():null}
        ${"anthropic"===this._pProvider?this._renderAnthropicFields():null}
        ${"openai_compatible"===this._pProvider?this._renderOpenAIFields():null}

        ${this._renderExcludedDomains()}

        ${this._providerError?F`<div class="modal__status modal__status--error">
              ⚠ ${this._providerError}
            </div>`:null}
        ${this._providerSuccess?F`<div class="modal__status modal__status--ok">
              ✓ Saved — reloading tracked products to apply the change.
            </div>`:null}

        <div class="trackform__actions">
          <button
            class="trackform__cancel"
            @click=${this._closeProviderEditor}
          >
            Close
          </button>
          <button
            class="add-button"
            @click=${this._saveProvider}
            ?disabled=${this._providerSaving}
          >
            ${this._providerSaving?"Saving…":"Save & apply"}
          </button>
        </div>
      </div>
    `}_renderExcludedDomains(){return F`
      <label class="trackform__field">
        <span>Excluded sites</span>
        <textarea
          class="provider__textarea"
          rows="3"
          placeholder="One site per line, e.g.&#10;amazon.de&#10;alza.cz"
          .value=${this._pExcludedDomains}
          @input=${e=>this._pExcludedDomains=e.target.value}
        ></textarea>
      </label>
      <div class="trackform__hint">
        Retailers listed here are dropped from every alternatives search
        and from Search &amp; add — useful for foreign sites that claim to
        ship to Iceland but you don't want to see. One hostname per line
        (e.g. <code>amazon.de</code>); subdomains are matched too.
      </div>
    `}_renderNoneInfo(){return F`
      <div class="trackform__hint">
        Free mode uses DuckDuckGo web search with deterministic price
        extraction — no API key and no per-call cost. AI-powered HTML
        parsing and richer alternative ranking are disabled.
      </div>
    `}_renderAnthropicFields(){return F`
      <label class="trackform__field">
        <span>Model</span>
        <select
          @change=${e=>this._pModel=e.target.value}
        >
          ${this._providerModels.map(e=>F`
              <option value=${e} ?selected=${this._pModel===e}>${e}</option>
            `)}
        </select>
      </label>
      <label class="trackform__field">
        <span>
          API key
          ${this._providerHasKey?F`<em>(leave blank to keep current)</em>`:null}
        </span>
        <input
          type="password"
          autocomplete="off"
          .value=${this._pApiKey}
          @input=${e=>this._pApiKey=e.target.value}
          placeholder=${this._providerHasKey?"•••••• stored — type to replace":"sk-ant-…"}
        />
      </label>
    `}_renderOpenAIFields(){return F`
      <label class="trackform__field">
        <span>Base URL</span>
        <input
          type="url"
          .value=${this._pBaseUrl}
          @input=${e=>this._pBaseUrl=e.target.value}
          placeholder="http://192.168.0.92:11434/v1"
        />
      </label>
      <label class="trackform__field">
        <span>Model</span>
        <input
          type="text"
          .value=${this._pModel}
          @input=${e=>this._pModel=e.target.value}
          placeholder="qwen2.5:7b"
        />
      </label>
      <label class="trackform__field">
        <span>API key <em>(optional for local endpoints)</em></span>
        <input
          type="password"
          autocomplete="off"
          .value=${this._pApiKey}
          @input=${e=>this._pApiKey=e.target.value}
          placeholder=${this._providerHasKey?"•••••• stored — type to replace":"optional"}
        />
      </label>

      <button
        type="button"
        class="provider__advtoggle"
        @click=${()=>this._providerAdvancedOpen=!this._providerAdvancedOpen}
      >
        ${this._providerAdvancedOpen?"▾":"▸"} Advanced (cost &amp; format)
      </button>
      ${this._providerAdvancedOpen?this._renderOpenAIAdvanced():null}
    `}_renderOpenAIAdvanced(){return F`
      <label class="trackform__field">
        <span>Input cost / Mtok (USD)</span>
        <input
          type="number"
          step="any"
          .value=${this._pInputCost}
          @input=${e=>this._pInputCost=e.target.value}
          placeholder="0"
        />
      </label>
      <label class="trackform__field">
        <span>Output cost / Mtok (USD)</span>
        <input
          type="number"
          step="any"
          .value=${this._pOutputCost}
          @input=${e=>this._pOutputCost=e.target.value}
          placeholder="0"
        />
      </label>
      <label class="trackform__field">
        <span>Max HTML chars</span>
        <input
          type="number"
          .value=${this._pMaxHtml}
          @input=${e=>this._pMaxHtml=e.target.value}
          placeholder="100000"
        />
      </label>
      <label class="ship-toggle provider__check">
        <input
          type="checkbox"
          .checked=${this._pForceJson}
          @change=${e=>this._pForceJson=e.target.checked}
        />
        <span>Force JSON response mode</span>
      </label>
      <label class="trackform__field">
        <span>Extra headers <em>(JSON object)</em></span>
        <textarea
          class="provider__textarea"
          rows="3"
          .value=${this._pExtraHeaders}
          @input=${e=>this._pExtraHeaders=e.target.value}
          placeholder='{"Authorization": "Bearer …"}'
        ></textarea>
      </label>
    `}_renderSummary(){const e=this._products,t=e.length,r=e.filter(e=>!0===e.inStock).length,i=e.filter(e=>null!==e.targetPrice&&null!==e.price&&e.price<=e.targetPrice).length,s=e.filter(e=>e.discontinued).length,o=(e,t,r)=>F`
      <div class="stat ${r}">
        <span class="stat__value">${t}</span>
        <span class="stat__label">${e}</span>
      </div>
    `;return F`
      <div class="summary">
        ${o("Tracked",t,"stat--total")}
        ${o("In stock",r,"stat--stock")}
        ${o("Below target",i,"stat--target")}
        ${o("Discontinued",s,"stat--disc")}
      </div>
    `}_renderToolbar(){return F`
      <div class="toolbar">
        <div class="toolbar__search">
          <input
            type="search"
            placeholder="Search products or retailers…"
            .value=${this._search}
            @input=${this._handleSearch}
            aria-label="Search products"
          />
        </div>
        <div class="toolbar__controls">
          <label class="sort-label">
            <span>Sort</span>
            <select @change=${this._handleSort} aria-label="Sort products">
              ${we.map(e=>F`
                  <option value=${e} ?selected=${this._sort===e}>
                    ${Se[e]}
                  </option>
                `)}
            </select>
          </label>
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
          <label
            class="ship-toggle"
            title="Hide products marked discontinued"
          >
            <input
              type="checkbox"
              .checked=${this._hideDiscontinued}
              @change=${this._handleToggleHideDiscontinued}
            />
            <span>Hide discontinued</span>
          </label>
        </div>
      </div>
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
    `}_renderGrid(){const e=this._visibleProducts();return 0===e.length?F`
        <div class="empty">
          <div class="empty__icon">🔍</div>
          <h2>No matches</h2>
          <p>No tracked products match your search or filters.</p>
        </div>
      `:F`
      <div class="grid">
        ${e.map(e=>F`
            <price-watch-card
              .product=${e}
              .onOpen=${this._handleOpen}
              .onRefreshAlternatives=${this._handleRefreshAlternatives}
              .refreshingAlternatives=${this._refreshingEntries.has(e.entryId)}
              .onRefreshNow=${this._handleRefreshNow}
              .refreshingNow=${this._refreshingNow.has(e.entryId)}
              .onSetTarget=${this._handleSetTarget}
              .onSetPaused=${this._handleSetPaused}
              .hideNonShipping=${this._hideNonShipping}
              .onRemoveListing=${this._handleRemoveListing}
              .onAddListing=${this._handleAddListing}
              .onEditListing=${this._handleEditListing}
              .onEditVariant=${this._handleEditVariant}
              .onAlert=${this._handleAlert}
              .onChangeSize=${this._handleChangeSize}
              .onExcludeAlternative=${this._handleExcludeAlternative}
              .excludedAltHosts=${this._hiddenAltHosts}
            ></price-watch-card>
          `)}
      </div>
    `}render(){const e=this._connected&&this._registry,t=this._products.length>0;return F`
      <div class="panel">
        ${this._renderHeader()}
        ${this._registryError?this._renderError():e?t?F`
              ${this._renderSummary()} ${this._renderToolbar()}
              ${this._renderGrid()}
            `:this._renderEmptyState():this._renderLoading()}
      </div>
      ${this._renderSearchModal()}
      ${this._renderProviderModal()}
      ${this._renderSelectorModal()}
      ${this._renderVariantModal()}
      ${this._renderAlertModal()}
    `}_renderAlertModal(){if(!this._alertOpen||!this._alertProduct)return null;const e=this._alertProduct,t=null!=e.targetPrice,r=[{key:"back_in_stock",label:"Back in stock",hint:"When this product returns to stock"},{key:"below_target",label:"Target price hit",hint:t?`When the price reaches your target (${e.targetPrice})`:"Set a target price on this product first",disabled:!t},{key:"price_drop",label:"Any price drop",hint:"Every time the price drops"}];return F`
      <div
        class="modal-backdrop"
        @click=${this._onAlertBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Create a price alert"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>🔔 Alert me</h2>
            <button class="modal__close" @click=${this._closeAlert} aria-label="Close">
              ✕
            </button>
          </div>
          <div class="trackform">
            <p class="sel__intro">
              Get a notification about <strong>${e.title}</strong>. This
              creates a Home Assistant automation for you — no YAML needed.
            </p>

            <div class="alert__section-label">When</div>
            <div class="alert__triggers">
              ${r.map(e=>F`
                  <label
                    class="alert__trigger ${this._alertTrigger===e.key?"alert__trigger--on":""} ${e.disabled?"alert__trigger--disabled":""}"
                  >
                    <input
                      type="radio"
                      name="pw-alert-trigger"
                      .checked=${this._alertTrigger===e.key}
                      ?disabled=${e.disabled}
                      @change=${()=>this._setAlertTrigger(e.key)}
                    />
                    <span class="alert__trigger-body">
                      <span class="alert__trigger-label">${e.label}</span>
                      <span class="alert__trigger-hint">${e.hint}</span>
                    </span>
                  </label>
                `)}
            </div>

            <div class="alert__section-label">Notify</div>
            ${this._alertLoading?F`<div class="modal__status">Loading your devices…</div>`:0===this._alertTargets.length?F`<div class="modal__status">
                  No notify devices found. Set up the Home Assistant mobile app
                  to get push notifications.
                </div>`:F`<div class="alert__targets">
                  ${this._alertTargets.map(e=>F`
                      <label class="alert__target">
                        <input
                          type="checkbox"
                          .checked=${this._alertSelected.has(e.service)}
                          @change=${()=>this._toggleAlertTarget(e.service)}
                        />
                        <span>${e.label}</span>
                      </label>
                    `)}
                </div>`}

            ${this._alertError?F`<div class="modal__status modal__status--error">
                  ⚠ ${this._alertError}
                </div>`:null}
            ${this._alertSaved?F`<div class="modal__status modal__status--ok">
                  ✓ Created "${this._alertSaved}". You'll be notified.
                </div>`:null}

            <div class="trackform__actions sel__actions">
              <button class="trackform__cancel" @click=${this._closeAlert}>
                Cancel
              </button>
              <button
                class="add-button"
                @click=${this._createAlert}
                ?disabled=${this._alertSaving||0===this._alertSelected.size}
              >
                ${this._alertSaving?"Creating…":"Create alert"}
              </button>
            </div>
          </div>
        </div>
      </div>
    `}_renderVariantModal(){if(!this._variantOpen||!this._varListing)return null;const e=this._varListing,t=this._varProduct,r=this._varGroups,i=this._matchedCombo(),s=this._varSelection.some(e=>!e);return F`
      <div
        class="modal-backdrop"
        @click=${this._onVariantBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Choose product variant"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>Choose variant</h2>
            <button
              class="modal__close"
              @click=${this._closeVariantPicker}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div class="trackform">
            <p class="sel__intro">
              For ${e.retailer||"this listing"}${t?F` on <strong>${t.title}</strong>`:null}. Pick the exact combination you want to track — the
              price below updates to match, and the tracker follows it from
              the next check on.
            </p>

            ${this._varLoading?F`<div class="modal__status">Reading variants…</div>`:null}
            ${this._varError?F`<div class="modal__status modal__status--error">
                  ⚠ ${this._varError}
                </div>`:null}
            ${this._varLoading||this._varError||this._varSupported?null:F`<div class="modal__status">
                  This page doesn't expose selectable variants, so there's
                  nothing to pin — it already tracks its only price.
                </div>`}

            ${r&&this._varSupported?F`
                  <div class="var__groups">
                    ${r.map((e,t)=>F`
                        <label class="trackform__field">
                          <span>${e.title}</span>
                          <select
                            class="var__select"
                            .value=${this._varSelection[t]??""}
                            @change=${e=>this._onVariantSelect(t,e.target.value)}
                          >
                            <option value="" ?selected=${!this._varSelection[t]}>
                              — choose —
                            </option>
                            ${e.choices.map(e=>F`<option
                                value=${e}
                                ?selected=${this._varSelection[t]===e}
                              >
                                ${e}
                              </option>`)}
                          </select>
                        </label>
                      `)}
                  </div>

                  <div class="var__preview">
                    ${i?F`<span class="var__price"
                            >${this._formatVariantPrice(i)}</span
                          >
                          ${i.in_stock?null:F`<span class="var__oos"
                                >out of stock</span
                              >`}`:s?F`<span class="var__hint"
                          >Pick an option in each group to see the price.</span
                        >`:F`<span class="var__hint var__hint--warn"
                          >That combination isn't available on the page.</span
                        >`}
                  </div>
                `:null}

            ${this._varSaveError?F`<div class="modal__status modal__status--error">
                  ⚠ ${this._varSaveError}
                </div>`:null}
            ${this._varSaved?F`<div class="modal__status modal__status--ok">
                  ✓ Saved — tracking this variant from the next check.
                </div>`:null}

            <div class="trackform__actions sel__actions">
              <button
                class="trackform__cancel"
                @click=${this._clearVariant}
                ?disabled=${this._varSaving||!this._varSupported}
                title="Revert to the page's default price"
              >
                Track default again
              </button>
              <button
                class="add-button"
                @click=${this._saveVariant}
                ?disabled=${this._varSaving||!this._varSupported||s||!i}
              >
                ${this._varSaving?"Saving…":"Track this variant"}
              </button>
            </div>
          </div>
        </div>
      </div>
    `}_formatVariantPrice(e){const t=e.currency||"";try{if(t)return new Intl.NumberFormat(void 0,{style:"currency",currency:t}).format(e.price)}catch{}return t?`${e.price} ${t}`:`${e.price}`}_renderSelectorModal(){if(!this._selectorOpen||!this._selListing)return null;const e=this._selListing,t=this._selProduct,r=e.url??"",i=this._selTestResult;return F`
      <div
        class="modal-backdrop"
        @click=${this._onSelectorBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Advanced price selector"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>Custom price selector</h2>
            <button
              class="modal__close"
              @click=${this._closeSelectorEditor}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div class="trackform">
            <p class="sel__intro">
              For ${e.retailer||"this listing"}${t?F` on <strong>${t.title}</strong>`:null}. Use this when the automatic price reader can't
              find the price. Open the page in your browser, press
              <kbd>F12</kbd>, right-click the price →
              <em>Copy → Copy selector</em>, and paste it below — or use
              the point-and-click picker further down.
            </p>
            ${r?F`<div class="sel__url" title=${r}>${r}</div>`:F`<div class="modal__status modal__status--error">
                  ⚠ This listing has no URL, so Test won't work.
                </div>`}

            <label class="trackform__field">
              <span>Price selector <em>(CSS)</em></span>
              <input
                type="text"
                .value=${this._selPriceSelector}
                @input=${this._onSelPriceInput}
                placeholder=".product-price .amount  (or  span#price@content)"
                spellcheck="false"
                autocapitalize="off"
              />
            </label>
            <label class="trackform__field">
              <span>Title selector <em>(optional — defaults to h1)</em></span>
              <input
                type="text"
                .value=${this._selTitleSelector}
                @input=${this._onSelTitleInput}
                placeholder="h1"
                spellcheck="false"
                autocapitalize="off"
              />
            </label>

            <div class="sel__test-row">
              <button
                class="sel__test-btn"
                @click=${this._runSelectorTest}
                ?disabled=${this._selTesting||!r}
              >
                ${this._selTesting?"Testing…":"Test on live page"}
              </button>
              <span class="sel__hint"
                >Append <code>@attr</code> to read an attribute, e.g.
                <code>meta[itemprop=price]@content</code>.</span
              >
            </div>

            ${this._selTestError?F`<div class="modal__status modal__status--error">
                  ⚠ ${this._selTestError}
                </div>`:null}
            ${i?this._renderSelectorTestResult(i):null}

            ${this._renderBookmarklet()}

            <label class="trackform__field">
              <span>
                Request cookies <em>(optional — for bot-walled sites)</em>
                ${e.hasCookies?F`<span class="sel__cookies-set"
                      >✓ cookies currently set</span
                    >`:null}
              </span>
              <textarea
                rows="3"
                .value=${this._selCookies}
                @input=${this._onSelCookiesInput}
                placeholder=${e.hasCookies?"Leave blank to keep current cookies, or paste new ones to replace":"session-id=123-456; ubid=ABC; i18n-prefs=GBP"}
                spellcheck="false"
                autocapitalize="off"
              ></textarea>
            </label>
            <p class="sel__hint">
              Paste the page's <code>Cookie</code> header (F12 → Network →
              any request → Request Headers → <em>Cookie</em>) to reach
              content behind Cloudflare / Amazon session walls. Stored
              separately from the selector — saving a selector won't erase
              cookies and vice-versa. Leave blank to keep existing cookies;
              cookies expire, so re-paste when a site starts failing.
            </p>

            ${this._selSaveError?F`<div class="modal__status modal__status--error">
                  ⚠ ${this._selSaveError}
                </div>`:null}
            ${this._selSaved?F`<div class="modal__status modal__status--ok">
                  ✓ Saved — the listing will use it on the next check.
                </div>`:null}

            <div class="trackform__actions sel__actions">
              <button
                class="trackform__cancel"
                @click=${this._clearSelector}
                ?disabled=${this._selSaving}
                title="Revert to automatic extraction (clears selector + cookies)"
              >
                Reset to automatic
              </button>
              <button
                class="add-button"
                @click=${this._saveSelector}
                ?disabled=${this._selSaving||!this._selPriceSelector.trim()&&!this._selCookies.trim()}
              >
                ${this._selSaving?"Saving…":"Save"}
              </button>
            </div>
          </div>
        </div>
      </div>
    `}_renderSelectorTestResult(e){const t=e.price,r=e.title;return F`
      <div class="sel__result">
        <div class="sel__result-head">
          Tested${e.page_title?F` — <span class="sel__page-title">${e.page_title}</span>`:null}
        </div>
        <div class="sel__result-row">
          <span class="sel__result-label">Price</span>
          ${t.found?F`<span class="sel__result-ok">
                  ${null!==t.value&&void 0!==t.value?F`<strong>${t.value}</strong>`:F`<em>matched, but not a number</em>`}
                </span>
                <code class="sel__raw">${t.raw}</code>`:F`<span class="sel__result-bad"
                >No match${t.error?F` — ${t.error}`:null}</span
              >`}
        </div>
        ${r?F`<div class="sel__result-row">
              <span class="sel__result-label">Title</span>
              ${r.found?F`<code class="sel__raw">${r.raw}</code>`:F`<span class="sel__result-bad">No match</span>`}
            </div>`:null}
        ${!t.found||null!==t.value&&void 0!==t.value?null:F`<p class="sel__warn">
              The element matched but no number could be parsed from it. Try a
              more specific selector, or append <code>@content</code> /
              <code>@data-price</code> to read a price attribute.
            </p>`}
      </div>
    `}_renderBookmarklet(){const e=this._bookmarkletHref();return F`
      <details
        class="sel__bm"
        ?open=${this._selBookmarkletOpen}
        @toggle=${e=>this._selBookmarkletOpen=e.target.open}
      >
        <summary>Point-and-click picker (bookmarklet)</summary>
        <div class="sel__bm-body">
          <p>
            Drag this button to your bookmarks bar. Then, on the retailer's
            product page, click the bookmark and click the price — its CSS
            selector is copied to your clipboard. Paste it above.
            <kbd>Esc</kbd> cancels.
          </p>
          <p>
            <a class="sel__bm-link" href=${e} @click=${e=>e.preventDefault()}
              >📍 Pick price selector</a
            >
          </p>
          <p class="sel__hint">
            Can't drag it? Copy the code and make a bookmark whose URL is this:
          </p>
          <div class="sel__bm-copy">
            <button class="sel__test-btn" @click=${this._copyBookmarklet}>
              Copy bookmarklet code
            </button>
          </div>
          <textarea
            class="sel__bm-code"
            readonly
            rows="3"
            @click=${e=>e.target.select()}
          >${e}</textarea>
        </div>
      </details>
    `}}PriceWatchPanel.HIDE_NONSHIP_KEY="price-watch:hide-non-shipping",PriceWatchPanel.SORT_KEY="price-watch:sort",PriceWatchPanel.HIDE_DISCONTINUED_KEY="price-watch:hide-discontinued",PriceWatchPanel.HIDE_NONSHOPS_KEY="price-watch:hide-non-shops",PriceWatchPanel.styles=a`
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
    .add-button:disabled {
      opacity: 0.5;
      cursor: default;
      filter: none;
    }
    .add-button--secondary {
      background: transparent;
      color: var(--primary-color, #03a9f4);
      border: 1px solid var(--primary-color, #03a9f4);
    }

    /* --- Search & add modal --- */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 48px 16px;
      z-index: 1000;
      overflow-y: auto;
    }
    .modal {
      width: 100%;
      max-width: 560px;
      background: var(--card-background-color, #fff);
      border-radius: 16px;
      box-shadow: 0 12px 48px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
      max-height: calc(100vh - 96px);
      overflow: hidden;
    }
    .modal__head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .modal__head h2 {
      margin: 0;
      font-size: 1.2rem;
      font-weight: 500;
    }
    .modal__close {
      background: none;
      border: none;
      font-size: 1.1rem;
      cursor: pointer;
      color: var(--secondary-text-color, #757575);
      padding: 4px 8px;
      border-radius: 8px;
      line-height: 1;
    }
    .modal__close:hover {
      background: var(--divider-color, #e0e0e0);
    }
    .modal__searchbar {
      display: flex;
      gap: 8px;
      padding: 16px 20px;
    }
    .modal__searchinput {
      flex: 1;
      box-sizing: border-box;
      padding: 10px 14px;
      font-size: 0.95rem;
      color: var(--primary-text-color, #212121);
      background: var(--primary-background-color, #fafafa);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      outline: none;
    }
    .modal__searchinput:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .modal__status {
      padding: 8px 20px 20px;
      color: var(--secondary-text-color, #757575);
      font-size: 0.9rem;
    }
    .modal__status--error {
      color: var(--error-color, #f44336);
    }
    .modal__status--ok {
      color: var(--success-color, #4caf50);
    }
    .modal__engine {
      padding: 0 20px 8px;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--secondary-text-color, #9e9e9e);
    }
    .results-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .results-bar .modal__engine {
      padding-bottom: 0;
    }
    .results-bar__toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 0 20px 8px;
      font-size: 0.78rem;
      color: var(--secondary-text-color, #757575);
      cursor: pointer;
      white-space: nowrap;
    }
    .results-bar__toggle input {
      cursor: pointer;
    }
    .results {
      list-style: none;
      margin: 0;
      padding: 0 12px 16px;
      overflow-y: auto;
    }
    .results__row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 8px;
      border-radius: 12px;
    }
    .results__row:hover {
      background: var(--primary-background-color, #f5f5f5);
    }
    .results__thumb {
      flex: 0 0 48px;
      width: 48px;
      height: 48px;
      border-radius: 8px;
      overflow: hidden;
      background: var(--primary-background-color, #f0f0f0);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .results__thumb img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .results__thumb-ph {
      font-size: 22px;
      opacity: 0.5;
    }
    .results__info {
      flex: 1;
      min-width: 0;
    }
    .results__title {
      font-size: 0.9rem;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .results__title--link {
      display: block;
      color: inherit;
      text-decoration: none;
      cursor: pointer;
    }
    .results__title--link:hover {
      color: var(--primary-color, #03a9f4);
      text-decoration: underline;
    }
    .results__ext {
      font-size: 0.72rem;
      opacity: 0.6;
      margin-left: 2px;
    }
    .results__meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 2px;
      flex-wrap: wrap;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
    }
    .results__price {
      font-weight: 600;
      color: var(--primary-text-color, #212121);
    }
    .results__ship {
      font-size: 0.68rem;
      padding: 1px 6px;
      border-radius: 999px;
    }
    .results__ship--yes {
      background: rgba(76, 175, 80, 0.16);
      color: var(--success-color, #4caf50);
    }
    .results__ship--no {
      background: rgba(158, 158, 158, 0.18);
      color: var(--secondary-text-color, #9e9e9e);
    }
    .results__kind {
      font-size: 0.68rem;
      padding: 1px 6px;
      border-radius: 999px;
    }
    .results__kind--info {
      background: rgba(255, 152, 0, 0.16);
      color: var(--warning-color, #ff9800);
    }
    /* De-emphasize rows that are clearly not a store. */
    .results__row--muted .results__thumb,
    .results__row--muted .results__title {
      opacity: 0.6;
    }
    .results__notes {
      font-size: 0.76rem;
      color: var(--secondary-text-color, #9e9e9e);
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .results__add {
      flex: 0 0 auto;
      padding: 6px 14px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      border: none;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 500;
      cursor: pointer;
    }
    .results__add:hover {
      filter: brightness(1.1);
    }
    .results__actions {
      flex: 0 0 auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
      align-items: stretch;
    }
    .results__exclude {
      padding: 5px 12px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      font-size: 0.74rem;
      cursor: pointer;
      white-space: nowrap;
    }
    .results__exclude:hover:not(:disabled) {
      color: var(--error-color, #f44336);
      border-color: var(--error-color, #f44336);
    }
    .results__exclude:disabled {
      opacity: 0.6;
      cursor: default;
    }

    /* --- Track-this confirm form --- */
    .trackform {
      padding: 16px 20px 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .trackform__hint {
      font-size: 0.85rem;
      color: var(--secondary-text-color, #757575);
    }
    .trackform__field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
    }
    .trackform__field em {
      font-style: normal;
      opacity: 0.7;
    }
    .trackform__field input,
    .trackform__field select,
    .trackform__field textarea {
      box-sizing: border-box;
      width: 100%;
      padding: 9px 12px;
      font-size: 0.9rem;
      font-family: inherit;
      color: var(--primary-text-color, #212121);
      background: var(--primary-background-color, #fafafa);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 10px;
      outline: none;
    }
    .trackform__field input:focus,
    .trackform__field select:focus,
    .trackform__field textarea:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .provider__textarea {
      resize: vertical;
      min-height: 56px;
    }
    .provider__advtoggle {
      align-self: flex-start;
      background: none;
      border: none;
      padding: 2px 0;
      font-size: 0.82rem;
      font-weight: 500;
      color: var(--primary-color, #03a9f4);
      cursor: pointer;
    }
    .provider__check {
      align-self: flex-start;
    }
    .trackform__actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 4px;
    }
    .trackform__cancel {
      padding: 8px 16px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      font-size: 0.875rem;
      cursor: pointer;
    }
    .trackform__cancel:hover {
      background: var(--primary-background-color, #f5f5f5);
    }

    /* --- Advanced price-selector editor --- */
    .sel__intro {
      margin: 0 0 4px;
      font-size: 0.85rem;
      line-height: 1.45;
      color: var(--secondary-text-color, #757575);
    }
    .sel__intro kbd,
    .sel__bm-body kbd {
      font-family: monospace;
      font-size: 0.78rem;
      padding: 1px 5px;
      border: 1px solid var(--divider-color, #d0d0d0);
      border-radius: 4px;
      background: var(--primary-background-color, #f5f5f5);
    }
    .sel__url {
      font-family: monospace;
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      padding: 4px 8px;
      background: var(--primary-background-color, #f5f5f5);
      border-radius: 6px;
    }
    .sel__test-row {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .sel__test-btn {
      padding: 7px 14px;
      background: var(--primary-color, #1976d2);
      color: #fff;
      border: none;
      border-radius: 999px;
      font-size: 0.85rem;
      cursor: pointer;
    }
    .sel__test-btn:disabled {
      opacity: 0.5;
      cursor: default;
    }
    .sel__hint {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #9e9e9e);
    }
    .sel__cookies-set {
      font-size: 0.72rem;
      font-style: normal;
      font-weight: 600;
      color: var(--success-color, #4caf50);
      margin-left: 0.4rem;
    }
    .sel__hint code,
    .sel__result code,
    .sel__warn code {
      font-family: monospace;
      font-size: 0.78rem;
      background: var(--primary-background-color, #f0f0f0);
      padding: 0 3px;
      border-radius: 3px;
    }
    .sel__result {
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .sel__result-head {
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--secondary-text-color, #9e9e9e);
    }
    .sel__page-title {
      text-transform: none;
      letter-spacing: 0;
    }
    .sel__result-row {
      display: flex;
      align-items: baseline;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 0.85rem;
    }
    .sel__result-label {
      flex: 0 0 44px;
      color: var(--secondary-text-color, #757575);
    }
    .sel__result-ok strong {
      font-size: 1.05rem;
      color: var(--success-color, #2e7d32);
    }
    .sel__result-bad {
      color: var(--error-color, #c62828);
    }
    .sel__raw {
      font-family: monospace;
      font-size: 0.78rem;
      color: var(--primary-text-color, #212121);
      word-break: break-all;
    }
    .sel__warn {
      margin: 0;
      font-size: 0.78rem;
      color: var(--secondary-text-color, #757575);
      line-height: 1.4;
    }
    .sel__bm {
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      padding: 0 12px;
    }
    .sel__bm summary {
      cursor: pointer;
      padding: 10px 0;
      font-size: 0.85rem;
      font-weight: 600;
    }
    .sel__bm-body {
      padding-bottom: 12px;
      font-size: 0.82rem;
      line-height: 1.45;
      color: var(--secondary-text-color, #757575);
    }
    .sel__bm-body p {
      margin: 0 0 8px;
    }
    .sel__bm-link {
      display: inline-block;
      padding: 6px 12px;
      background: var(--primary-background-color, #f0f0f0);
      border: 1px dashed var(--primary-color, #1976d2);
      border-radius: 8px;
      color: var(--primary-color, #1976d2);
      text-decoration: none;
      font-weight: 600;
      cursor: grab;
    }
    .sel__bm-code {
      width: 100%;
      box-sizing: border-box;
      font-family: monospace;
      font-size: 0.7rem;
      resize: vertical;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 6px;
    }
    .sel__actions {
      justify-content: space-between;
    }

    /* --- Variant picker --- */
    .var__groups {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .var__select {
      width: 100%;
      box-sizing: border-box;
      padding: 8px 10px;
      font: inherit;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #c0c0c0);
      border-radius: 8px;
    }
    .var__preview {
      margin-top: 14px;
      padding: 12px 14px;
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 10px;
      display: flex;
      align-items: baseline;
      gap: 10px;
      min-height: 24px;
    }
    .var__price {
      font-size: 1.4rem;
      font-weight: 600;
      line-height: 1.1;
    }
    .var__oos {
      font-size: 0.8rem;
      color: var(--error-color, #c62828);
    }
    .var__hint {
      color: var(--secondary-text-color, #757575);
      font-size: 0.9rem;
    }
    .var__hint--warn {
      color: var(--warning-color, #f57c00);
    }

    /* --- Alert ("notify me") dialog --- */
    .alert__section-label {
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--secondary-text-color, #757575);
      margin: 14px 0 6px;
    }
    .alert__triggers {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .alert__trigger {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 10px;
      cursor: pointer;
    }
    .alert__trigger--on {
      border-color: var(--primary-color, #03a9f4);
      background: rgba(3, 169, 244, 0.07);
    }
    .alert__trigger--disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .alert__trigger input {
      margin-top: 3px;
    }
    .alert__trigger-body {
      display: flex;
      flex-direction: column;
      gap: 1px;
    }
    .alert__trigger-label {
      font-size: 0.92rem;
      font-weight: 500;
    }
    .alert__trigger-hint {
      font-size: 0.78rem;
      color: var(--secondary-text-color, #757575);
    }
    .alert__targets {
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-height: 180px;
      overflow-y: auto;
    }
    .alert__target {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 2px;
      font-size: 0.9rem;
      cursor: pointer;
    }

    /* --- Summary stat bar --- */
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .stat {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 12px 16px;
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 12px;
      border-left-width: 4px;
    }
    .stat__value {
      font-size: 1.5rem;
      font-weight: 600;
      line-height: 1.1;
    }
    .stat__label {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .stat--total {
      border-left-color: var(--primary-color, #03a9f4);
    }
    .stat--stock {
      border-left-color: var(--success-color, #4caf50);
    }
    .stat--target {
      border-left-color: var(--warning-color, #ff9800);
    }
    .stat--disc {
      border-left-color: var(--secondary-text-color, #9e9e9e);
    }

    /* --- Toolbar --- */
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .toolbar__search {
      flex: 1 1 240px;
      min-width: 180px;
    }
    .toolbar__search input {
      width: 100%;
      box-sizing: border-box;
      padding: 8px 12px;
      font-size: 0.875rem;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      outline: none;
    }
    .toolbar__search input:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .toolbar__controls {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }
    .sort-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
      white-space: nowrap;
    }
    .sort-label select {
      padding: 6px 10px;
      font-size: 0.8rem;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      cursor: pointer;
      outline: none;
    }
    .sort-label select:focus {
      border-color: var(--primary-color, #03a9f4);
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
  `,e([he()],PriceWatchPanel.prototype,"_products",void 0),e([he()],PriceWatchPanel.prototype,"_registry",void 0),e([he()],PriceWatchPanel.prototype,"_registryError",void 0),e([he()],PriceWatchPanel.prototype,"_connected",void 0),e([he()],PriceWatchPanel.prototype,"_refreshingEntries",void 0),e([he()],PriceWatchPanel.prototype,"_hideNonShipping",void 0),e([he()],PriceWatchPanel.prototype,"_search",void 0),e([he()],PriceWatchPanel.prototype,"_sort",void 0),e([he()],PriceWatchPanel.prototype,"_hideDiscontinued",void 0),e([he()],PriceWatchPanel.prototype,"_refreshingNow",void 0),e([he()],PriceWatchPanel.prototype,"_searchOpen",void 0),e([he()],PriceWatchPanel.prototype,"_searchQuery",void 0),e([he()],PriceWatchPanel.prototype,"_searchLoading",void 0),e([he()],PriceWatchPanel.prototype,"_searchResults",void 0),e([he()],PriceWatchPanel.prototype,"_searchEngine",void 0),e([he()],PriceWatchPanel.prototype,"_searchRan",void 0),e([he()],PriceWatchPanel.prototype,"_searchError",void 0),e([he()],PriceWatchPanel.prototype,"_excludingHosts",void 0),e([he()],PriceWatchPanel.prototype,"_hiddenAltHosts",void 0),e([he()],PriceWatchPanel.prototype,"_hideNonShops",void 0),e([he()],PriceWatchPanel.prototype,"_trackTarget",void 0),e([he()],PriceWatchPanel.prototype,"_trackName",void 0),e([he()],PriceWatchPanel.prototype,"_trackUrl",void 0),e([he()],PriceWatchPanel.prototype,"_trackTargetPrice",void 0),e([he()],PriceWatchPanel.prototype,"_tracking",void 0),e([he()],PriceWatchPanel.prototype,"_trackError",void 0),e([he()],PriceWatchPanel.prototype,"_providerOpen",void 0),e([he()],PriceWatchPanel.prototype,"_providerLoading",void 0),e([he()],PriceWatchPanel.prototype,"_providerSaving",void 0),e([he()],PriceWatchPanel.prototype,"_providerError",void 0),e([he()],PriceWatchPanel.prototype,"_providerSuccess",void 0),e([he()],PriceWatchPanel.prototype,"_providerAdvancedOpen",void 0),e([he()],PriceWatchPanel.prototype,"_pProvider",void 0),e([he()],PriceWatchPanel.prototype,"_pApiKey",void 0),e([he()],PriceWatchPanel.prototype,"_pModel",void 0),e([he()],PriceWatchPanel.prototype,"_pBaseUrl",void 0),e([he()],PriceWatchPanel.prototype,"_pInputCost",void 0),e([he()],PriceWatchPanel.prototype,"_pOutputCost",void 0),e([he()],PriceWatchPanel.prototype,"_pMaxHtml",void 0),e([he()],PriceWatchPanel.prototype,"_pForceJson",void 0),e([he()],PriceWatchPanel.prototype,"_pExtraHeaders",void 0),e([he()],PriceWatchPanel.prototype,"_pExcludedDomains",void 0),e([he()],PriceWatchPanel.prototype,"_providerHasKey",void 0),e([he()],PriceWatchPanel.prototype,"_providerModels",void 0),e([he()],PriceWatchPanel.prototype,"_selectorOpen",void 0),e([he()],PriceWatchPanel.prototype,"_selPriceSelector",void 0),e([he()],PriceWatchPanel.prototype,"_selTitleSelector",void 0),e([he()],PriceWatchPanel.prototype,"_selCookies",void 0),e([he()],PriceWatchPanel.prototype,"_selTesting",void 0),e([he()],PriceWatchPanel.prototype,"_selTestResult",void 0),e([he()],PriceWatchPanel.prototype,"_selTestError",void 0),e([he()],PriceWatchPanel.prototype,"_selSaving",void 0),e([he()],PriceWatchPanel.prototype,"_selSaveError",void 0),e([he()],PriceWatchPanel.prototype,"_selSaved",void 0),e([he()],PriceWatchPanel.prototype,"_selBookmarkletOpen",void 0),e([he()],PriceWatchPanel.prototype,"_variantOpen",void 0),e([he()],PriceWatchPanel.prototype,"_varLoading",void 0),e([he()],PriceWatchPanel.prototype,"_varError",void 0),e([he()],PriceWatchPanel.prototype,"_varGroups",void 0),e([he()],PriceWatchPanel.prototype,"_varCombos",void 0),e([he()],PriceWatchPanel.prototype,"_varSelection",void 0),e([he()],PriceWatchPanel.prototype,"_varSupported",void 0),e([he()],PriceWatchPanel.prototype,"_varSaving",void 0),e([he()],PriceWatchPanel.prototype,"_varSaveError",void 0),e([he()],PriceWatchPanel.prototype,"_varSaved",void 0),e([he()],PriceWatchPanel.prototype,"_alertOpen",void 0),e([he()],PriceWatchPanel.prototype,"_alertTrigger",void 0),e([he()],PriceWatchPanel.prototype,"_alertTargets",void 0),e([he()],PriceWatchPanel.prototype,"_alertSelected",void 0),e([he()],PriceWatchPanel.prototype,"_alertLoading",void 0),e([he()],PriceWatchPanel.prototype,"_alertSaving",void 0),e([he()],PriceWatchPanel.prototype,"_alertError",void 0),e([he()],PriceWatchPanel.prototype,"_alertSaved",void 0),customElements.get("price-watch-panel")||customElements.define("price-watch-panel",PriceWatchPanel);export{PriceWatchPanel};
