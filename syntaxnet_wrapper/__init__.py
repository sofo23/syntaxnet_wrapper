import subprocess
import os
import six
import time
import signal

from os.path import join, dirname, abspath
from fcntl import fcntl, F_SETFL, F_GETFD

__all__ = ['parser', 'tagger']


class SyntaxNetWrapper(object):
    def __del__(self):
        self.stop()


    def start(self):
        rundir = join(pwd, 'models/syntaxnet/bazel-bin/syntaxnet/parser_eval.runfiles')
        command = ['python', self.run_filename, self.model_path, self.context_path]

        env = os.environ.copy()
        env['PYTHONPATH'] = rundir
        subproc_args = {'stdin': subprocess.PIPE, 'stdout': subprocess.PIPE,
                        'stderr': subprocess.STDOUT, 'cwd': pwd,
                        'env': env, 'close_fds': True}
        self.process = subprocess.Popen(command, shell=False, **subproc_args)
        self.out = self.process.stdout
        self.din = self.process.stdin
        fcntl(self.out.fileno(), F_SETFL, fcntl(self.out.fileno(), F_GETFD) | os.O_NONBLOCK)
    

    def stop(self):
        self.din.close()
        try:
            self.process.send_signal(signal.SIGABRT)
            self.process.kill()
            self.process.wait()
        except OSError:
            pass


    def __init__(self, run_filename, model_name):
        pwd = dirname(abspath(__file__))
        context_path = join(pwd, context_path)

        self.model_name = model_name
        self.run_filename = run_filename

        if model_name == 'English-Parsey':
            model_path = 'models/syntaxnet'
            context_path = 'models/syntaxnet/syntaxnet/models/parsey_mcparseface/context.pbtxt'
        elif model_name == 'ZHTokenizer':
            model_path = 'models/syntaxnet/syntaxnet/models/parsey_universal/Chinese'
            context_path = 'models/syntaxnet/syntaxnet/models/parsey_universal/context-tokenize-zh.pbtxt'
        else:
            model_path = 'models/syntaxnet/syntaxnet/models/parsey_universal/{!s}'.format(model_name)
            context_path = 'models/syntaxnet/syntaxnet/models/parsey_universal/context.pbtxt'

        model_path = join(pwd, self.model_path)
        self.model_path = model_path
        self.context_path = context_path

        self.start()


    def wait_for(self, text):
        result = []
        while True:
            try:
                line = self.out.readline().decode('utf-8').strip()[:-1]
                if text == result:
                    return result
                result.append(line)
            except:
                pass


    def query(self, text, returnRaw=False):
        self.wait_for('## input content:')
        
        ## push data
        self.din.write(text.encode('utf8') + six.b('\n'))
        self.din.flush()

        self.wait_for('## result start')
        result = self.wait_for('## result end')
        
        if returnRaw:
            return '\n'.join(results).strip() + "\n"
        return [r.split('\t') for r in results[:-2]]


    def list_models(self):
        pwd = dirname(abspath(__file__))
        model_path = os.path.join(pwd, 'models/syntaxnet/syntaxnet/models/parsey_universal')
        files = os.listdir(model_path)
        models = []
        for fn in files:
            if os.path.isdir(os.path.join(model_path, fn)):
                models.append(fn)
        models.append('English-Parsey')
        return sorted(models)


class SyntaxNetTokenizer(SyntaxNetWrapper):
    def __init__(self, model_name='ZHTokenizer'):
        super(SyntaxNetTokenizer, self).__init__('tokenizer_eval_forever.py', model_name)

    def query(self, text):
        return super(SyntaxNetTokenizer, self).query(text, returnRaw=True)


class SyntaxNetMorpher(SyntaxNetWrapper):
    def __init__(self, model_name='English'):
        if model_name == 'Chinese':
            self.tokenizer = SyntaxNetTokenizer()
        else:
            self.tokenizer = None
        super(SyntaxNetMorpher, self).__init__('morpher_eval_forever.py', model_name)

    def query(self, text, returnRaw=False):
        if self.tokenizer:
            tokenized_text = self.tokenizer.query(text)
        else:
            tokenized_text = text
        return super(SyntaxNetMorpher, self).query(tokenized_text, returnRaw)

    def query_raw(self, tokenized_text, returnRaw=False):
        return super(SyntaxNetMorpher, self).query(tokenized_text, returnRaw)


class SyntaxNetTagger(SyntaxNetWrapper):
    def __init__(self, model_name='English-Parsey', **kwargs):
        if model_name == 'English-Parsey':
            self.morpher = None
        elif 'morpher' in kwargs:
            self.morpher = kwargs['morpher']
        else:
            self.morpher = SyntaxNetMorpher(model_name)
        super(SyntaxNetTagger, self).__init__('tagger_eval_forever.py', model_name)

    def query(self, morphed_text, returnRaw=False):
        if self.morpher:
            conll_text = self.morpher.query(morphed_text, returnRaw=True)
        else:
            conll_text = morphed_text
        return super(SyntaxNetTagger, self).query(conll_text, returnRaw)

    def query_raw(self, conll_text, returnRaw=False):
        return super(SyntaxNetTagger, self).query(conll_text, returnRaw)


class SyntaxNetParser(SyntaxNetWrapper):
    def __init__(self, model_name='English-Parsey', **kwargs):
        if 'tagger' in kwargs:
            self.tagger = kwargs['tagger']
            self.morpher = self.tagger.morpher
        else:
            if model_name == 'English-Parsey':
                self.morpher = None
            elif 'morpher' in kwargs:
                self.morpher = kwargs['morpher']
            else:
                self.morpher = SyntaxNetMorpher(model_name)
            self.tagger = SyntaxNetTagger(model_name, morpher=self.morpher)
        super(SyntaxNetParser, self).__init__('parser_eval_forever.py', model_name)

    def query(self, text, returnRaw=False):
        conll_text = self.tagger.query(text, returnRaw=True)
        return super(SyntaxNetParser, self).query(conll_text, returnRaw)

    def query_raw(self, conll_text, returnRaw=False):
        return super(SyntaxNetParser, self).query(conll_text, returnRaw)


language_code_to_model_name = {
    'ar': 'Arabic',
    'eu': 'Basque',
    'bg': 'Bulgarian',
    'ca': 'Catalan',
    'zh': 'Chinese',
    'zh-tw': 'Chinese',
    'zh-cn': 'Chinese',
    'hr': 'Croatian',
    'cs': 'Czech',
    'da': 'Danish',
    'nl': 'Dutch',
    'en': 'English-Parsey',
    'et': 'Estonian',
    'fi': 'Finnish',
    'fr': 'French',
    'gl': 'Galician',
    'de': 'German',
    'el': 'Greek',
    'iw': 'Hebrew',
    'hi': 'Hindi',
    'hu': 'Hungarian',
    'id': 'Indonesian',
    'ga': 'Irish',
    'it': 'Italian',
    'kk': 'Kazakh',
    'la': 'Latin',
    'lv': 'Latvian',
    'no': 'Norwegian',
    'fa': 'Persian',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'ro': 'Romanian',
    'ru': 'Russian',
    'sl': 'Slovenian',
    'es': 'Spanish',
    'sv': 'Swedish',
    'ta': 'Tamil',
    'tr': 'Turkish',
}


class Tagger(object):
    cached = {}

    def __del__(self):
        for code in self.cached:
            tmp = self.cached[code]
            self.cached[code] = None
            del tmp

    def __getitem__(self, code):
        if code not in language_code_to_model_name:
            raise ValueError('Invalid language code for tagger: {}'.format(code))
        lang = language_code_to_model_name[code]
        if code in self.cached:
            return self.cached[code]
        self.cached[code] = SyntaxNetTagger(lang)
        return self.cached[code]

tagger = Tagger()


class Parser(object):
    cached = {}

    def __del__(self):
        for code in self.cached:
            tmp = self.cached[code]
            self.cached[code] = None
            del tmp

    def __getitem__(self, code):
        if code not in language_code_to_model_name:
            raise ValueError('Invalid language code for parser: {}'.format(code))
        lang = language_code_to_model_name[code]
        if code in self.cached:
            return self.cached[code]
        self.cached[code] = SyntaxNetParser(lang, tagger=tagger[code])
        return self.cached[code]

parser = Parser()


def parse_text(text, lang='en', returnRaw=True):
    lang = language_code_to_model_name[lang]
    tagger, parser = None, None
    try:
        tagger = SyntaxNetTagger(lang)
        parser = SyntaxNetParser(lang, tagger=tagger)
        result = parser.query(text, returnRaw)
        return result
    finally:
        del tagger, parser

def tag_text(text, lang='en', returnRaw=True):
    lang = language_code_to_model_name[lang]
    tagger = None
    try:
        tagger = SyntaxNetTagger(lang)
        result = tagger.query(text, returnRaw)
        return result
    finally:
        del tagger
