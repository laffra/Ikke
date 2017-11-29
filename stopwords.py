import re

WORDS_RE = re.compile('([^a-zA-Z])+')

WEB_WORDS = " pdf | gif | jpg | jpeg | https | http | org | gov | com | nl | index | html | doc | uid | rfc "
EMAIL_WORDS = " re | fwd | fw "
DUTCH_STOPWORDS = " op | de | den | voor | aan | af | al | als | bij | dan | dat | die | dit | een | en | er | had | heb | hem | het | hij | hoe | hun | ik | in | is | je | kan | me | men | met | mij | nog | nu | of | ons | ook | te | tot | uit | van | was | wat | we | wel | wij | zal | ze | zei | zij | zo | zou "
DATETIME_WORDS = " week | month | year | today | tomorrow | am | pm | jan | feb | mar | apr | may | jun jul aug | sep | oct | nov | dec | january | february | march | april | may | june | july | august | september | october | november | december | mon | tue | wed | thu | fri | sat | sun | [a-z]*day "
ENGLISH_STOPWORDS = " a | able | about | above | abst | accordance | according | accordingly | across | act | actually | added | adj | affected | affecting | affects | after | afterwards | again | against | ah | all | almost | alone | along | already | also | although | always | am | among | amongst | an | and | announce | another | any | anybody | anyhow | anymore | anyone | anything | anyway | anyways | anywhere | apparently | approximately | are | aren | arent | arise | around | as | aside | ask | asking | at | auth | available | away | awfully | b | back | be | became | because | become | becomes | becoming | been | before | beforehand | begin | beginning | beginnings | begins | behind | being | believe | below | beside | besides | between | beyond | biol | both | brief | briefly | but | by | c | ca | came | can | cannot | can't | cause | causes | certain | certainly | co | com | come | comes | contain | containing | contains | could | couldnt | d | date | did | didn't | different | do | does | doesn't | doing | done | don't | down | downwards | due | during | e | each | ed | edu | effect | eg | eight | eighty | either | else | elsewhere | end | ending | enough | especially | et | et-al | etc | even | ever | every | everybody | everyone | everything | everywhere | ex | except | f | far | few | ff | fifth | first | five | fix | followed | following | follows | for | former | formerly | forth | found | four | from | further | furthermore | g | gave | get | gets | getting | give | given | gives | giving | go | goes | gone | got | gotten | h | had | happens | hardly | has | hasn't | have | haven't | having | he | hed | hence | her | here | hereafter | hereby | herein | heres | hereupon | hers | herself | hes | hi | hid | him | himself | his | hither | home | how | howbeit | however | hundred | i | id | ie | if | i'll | im | immediate | immediately | importance | important | in | inc | indeed | index | information | instead | into | invention | inward | is | isn't | it | itd | it'll | its | itself | i've | j | just | k | keep	keeps | kept | kg | km | know | known | knows | l | largely | last | lately | later | latter | latterly | least | less | lest | let | lets | like | liked | likely | line | little | 'll | look | looking | looks | ltd | m | made | mainly | make | makes | many | may | maybe | me | mean | means | meantime | meanwhile | merely | mg | might | million | miss | ml | more | moreover | most | mostly | mr | mrs | much | mug | must | my | myself | n | na | name | namely | nay | nd | near | nearly | necessarily | necessary | need | needs | neither | never | nevertheless | new | next | nine | ninety | no | nobody | non | none | nonetheless | noone | nor | normally | nos | not | noted | nothing | now | nowhere | o | obtain | obtained | obviously | of | off | often | oh | ok | okay | old | omitted | on | once | one | ones | only | onto | or | ord | other | others | otherwise | ought | our | ours | ourselves | out | outside | over | overall | owing | own | p | page | pages | part | particular | particularly | past | per | perhaps | placed | please | plus | poorly | possible | possibly | potentially | pp | predominantly | present | previously | primarily | probably | promptly | proud | provides | put | q | que | quickly | quite | qv | r | ran | rather | rd | re | readily | really | recent | recently | ref | refs | regarding | regardless | regards | related | relatively | research | respectively | resulted | resulting | results | right | run | s | said | same | saw | say | saying | says | sec | section | see | seeing | seem | seemed | seeming | seems | seen | self | selves | sent | seven | several | shall | she | shed | she'll | shes | should | shouldn't | show | showed | shown | showns | shows | significant | significantly | similar | similarly | since | six | slightly | so | some | somebody | somehow | someone | somethan | something | sometime | sometimes | somewhat | somewhere | soon | sorry | specifically | specified | specify | specifying | still | stop | strongly | sub | substantially | successfully | such | sufficiently | suggest | sup | sure	t | take | taken | taking | tell | tends | th | than | thank | thanks | thanx | that | that'll | thats | that've | the | their | theirs | them | themselves | then | thence | there | thereafter | thereby | thered | therefore | therein | there'll | thereof | therere | theres | thereto | thereupon | there've | these | they | theyd | they'll | theyre | they've | think | this | those | thou | though | thoughh | thousand | throug | through | throughout | thru | thus | til | tip | to | together | too | took | toward | towards | tried | tries | truly | try | trying | ts | twice | two | u | un | under | unfortunately | unless | unlike | unlikely | until | unto | up | upon | ups | us | use | used | useful | usefully | usefulness | uses | using | usually | v | value | various | 've | very | via | viz | vol | vols | vs | w | want | wants | was | wasnt | way | we | wed | welcome | we'll | went | were | werent | we've | what | whatever | what'll | whats | when | whence | whenever | where | whereafter | whereas | whereby | wherein | wheres | whereupon | wherever | whether | which | while | whim | whither | who | whod | whoever | whole | who'll | whom | whomever | whos | whose | why | widely | willing | wish | with | within | without | wont | words | world | would | wouldnt | www | x | y | yes | yet | you | youd | you'll | your | youre | yours | yourself | yourselves | you've | z | zero "
UNDERSCORE_WORDS = " [^ ]*_[^ ]* "

STOPWORDS = '|'.join([
    WEB_WORDS,
    EMAIL_WORDS,
    DUTCH_STOPWORDS,
    DATETIME_WORDS,
    ENGLISH_STOPWORDS,
    UNDERSCORE_WORDS
])

STOPWORDS_RE = re.compile(STOPWORDS, flags=re.IGNORECASE)

SPACES_RE = re.compile('[ ]+')

IS_NUMBER_RE = re.compile('^[0-9]*$')


def is_stopword(word):
    return remove_stopwords(word) == []

def remove_stopwords(s):
    words = re.sub(WORDS_RE, '  ', s)
    contents = re.sub(STOPWORDS_RE, ' ', ' %s ' % words).strip()
    words = re.sub(SPACES_RE, ' ', contents.lower()).split()
    return [word for word in words if len(word) > 2 and not word.isdigit()]


if __name__ == '__main__':
    def t(s, expected):
        assert remove_stopwords(s) == expected, 'Error: input=%s expected=%s result=%s' % (
            repr(s),
            repr(expected),
            repr(remove_stopwords(s)))

    t('Re: Test', ['test'])
    t('This is a Test', ['test'])
    t('This is not a Test', ['test'])
    t('ABC12345', ['abc12345'])

    assert not is_stopword('ipse'), 'Should not be a stopword'
    assert not is_stopword('bruggen'), 'Should not be a stopword'
    assert not is_stopword('dog'), 'Should not be a stopword'

    assert is_stopword('de'), 'Should be a stopword'
    assert is_stopword('an'), 'Should be a stopword'
