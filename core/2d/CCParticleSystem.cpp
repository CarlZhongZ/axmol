/****************************************************************************
Copyright (c) 2008-2010 Ricardo Quesada
Copyright (c) 2010-2012 cocos2d-x.org
Copyright (c) 2011      Zynga Inc.
Copyright (c) 2013-2016 Chukong Technologies Inc.
Copyright (c) 2017-2018 Xiamen Yaji Software Co., Ltd.
Copyright (c) 2021 Bytedance Inc.

https://adxeproject.github.io/

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
****************************************************************************/

// ideas taken from:
//     . The ocean spray in your face [Jeff Lander]
//        http://www.double.co.nz/dust/col0798.pdf
//     . Building an Advanced Particle System [John van der Burg]
//        http://www.gamasutra.com/features/20000623/vanderburg_01.htm
//   . LOVE game engine
//        http://love2d.org/
//
//
// Radius mode support, from 71 squared
//        http://particledesigner.71squared.com/
//
// IMPORTANT: Particle Designer is supported by cocos2d, but
// 'Radius Mode' in Particle Designer uses a fixed emit rate of 30 hz. Since that can't be guaranteed in cocos2d,
//  cocos2d uses a another approach, but the results are almost identical.
//

#include "2d/CCParticleSystem.h"

#include <string>

#include "2d/CCParticleBatchNode.h"
#include "renderer/CCTextureAtlas.h"
#include "base/base64.h"
#include "base/ZipUtils.h"
#include "base/CCDirector.h"
#include "base/CCProfiling.h"
#include "base/ccUTF8.h"
#include "base/ccUtils.h"
#include "renderer/CCTextureCache.h"
#include "platform/CCFileUtils.h"

using namespace std;

NS_CC_BEGIN

// ideas taken from:
//     . The ocean spray in your face [Jeff Lander]
//        http://www.double.co.nz/dust/col0798.pdf
//     . Building an Advanced Particle System [John van der Burg]
//        http://www.gamasutra.com/features/20000623/vanderburg_01.htm
//   . LOVE game engine
//        http://love2d.org/
//
//
// Radius mode support, from 71 squared
//        http://particledesigner.71squared.com/
//
// IMPORTANT: Particle Designer is supported by cocos2d, but
// 'Radius Mode' in Particle Designer uses a fixed emit rate of 30 hz. Since that can't be guaranteed in cocos2d,
//  cocos2d uses a another approach, but the results are almost identical.
//

inline void normalize_point(float x, float y, particle_point* out)
{
    float n = x * x + y * y;
    // Already normalized.
    if (n == 1.0f)
        return;

    n = sqrt(n);
    // Too close to zero.
    if (n < MATH_TOLERANCE)
        return;

    n      = 1.0f / n;
    out->x = x * n;
    out->y = y * n;
}

/**
 A more effective random number generator function, made by ejoy2d.
 */
inline static float RANDOM_M11(unsigned int* seed)
{
    *seed = *seed * 134775813 + 1;
    union
    {
        uint32_t d;
        float f;
    } u;
    u.d = (((uint32_t)(*seed) & 0x7fff) << 8) | 0x40000000;
    return u.f - 3.0f;
}

ParticleData::ParticleData()
{
    memset(this, 0, sizeof(ParticleData));
}

bool ParticleData::init(int count)
{
    maxCount = count;

    posx               = (float*)malloc(count * sizeof(float));
    posy               = (float*)malloc(count * sizeof(float));
    startPosX          = (float*)malloc(count * sizeof(float));
    startPosY          = (float*)malloc(count * sizeof(float));
    colorR             = (float*)malloc(count * sizeof(float));
    colorG             = (float*)malloc(count * sizeof(float));
    colorB             = (float*)malloc(count * sizeof(float));
    colorA             = (float*)malloc(count * sizeof(float));
    deltaColorR        = (float*)malloc(count * sizeof(float));
    deltaColorG        = (float*)malloc(count * sizeof(float));
    deltaColorB        = (float*)malloc(count * sizeof(float));
    deltaColorA        = (float*)malloc(count * sizeof(float));
    size               = (float*)malloc(count * sizeof(float));
    deltaSize          = (float*)malloc(count * sizeof(float));
    rotation           = (float*)malloc(count * sizeof(float));
    staticRotation     = (float*)malloc(count * sizeof(float));
    deltaRotation      = (float*)malloc(count * sizeof(float));
    totalTimeToLive    = (float*)malloc(count * sizeof(float));
    timeToLive         = (float*)malloc(count * sizeof(float));
    animTimeDelta      = (float*)malloc(count * sizeof(float));
    animTimeLength     = (float*)malloc(count * sizeof(float));
    animIndex          = (unsigned short*)malloc(count * sizeof(unsigned short));
    animCellIndex      = (unsigned short*)malloc(count * sizeof(unsigned short));
    atlasIndex         = (unsigned int*)malloc(count * sizeof(unsigned int));

    modeA.dirX            = (float*)malloc(count * sizeof(float));
    modeA.dirY            = (float*)malloc(count * sizeof(float));
    modeA.radialAccel     = (float*)malloc(count * sizeof(float));
    modeA.tangentialAccel = (float*)malloc(count * sizeof(float));

    modeB.angle            = (float*)malloc(count * sizeof(float));
    modeB.degreesPerSecond = (float*)malloc(count * sizeof(float));
    modeB.deltaRadius      = (float*)malloc(count * sizeof(float));
    modeB.radius           = (float*)malloc(count * sizeof(float));

    return posx && posy && startPosY && startPosX && colorR && colorG && colorB && colorA && deltaColorR &&
           deltaColorG && deltaColorB && deltaColorA && size && deltaSize && rotation && deltaRotation && totalTimeToLive &&
           timeToLive && atlasIndex && modeA.dirX && modeA.dirY && modeA.radialAccel && modeA.tangentialAccel &&
           modeB.angle && modeB.degreesPerSecond && modeB.deltaRadius && modeB.radius;
}

void ParticleData::release()
{
    CC_SAFE_FREE(posx);
    CC_SAFE_FREE(posy);
    CC_SAFE_FREE(startPosX);
    CC_SAFE_FREE(startPosY);
    CC_SAFE_FREE(colorR);
    CC_SAFE_FREE(colorG);
    CC_SAFE_FREE(colorB);
    CC_SAFE_FREE(colorA);
    CC_SAFE_FREE(deltaColorR);
    CC_SAFE_FREE(deltaColorG);
    CC_SAFE_FREE(deltaColorB);
    CC_SAFE_FREE(deltaColorA);
    CC_SAFE_FREE(size);
    CC_SAFE_FREE(deltaSize);
    CC_SAFE_FREE(rotation);
    CC_SAFE_FREE(staticRotation);
    CC_SAFE_FREE(deltaRotation);
    CC_SAFE_FREE(totalTimeToLive);
    CC_SAFE_FREE(timeToLive);
    CC_SAFE_FREE(animTimeDelta);
    CC_SAFE_FREE(animTimeLength);
    CC_SAFE_FREE(animIndex);
    CC_SAFE_FREE(animCellIndex);
    CC_SAFE_FREE(atlasIndex);

    CC_SAFE_FREE(modeA.dirX);
    CC_SAFE_FREE(modeA.dirY);
    CC_SAFE_FREE(modeA.radialAccel);
    CC_SAFE_FREE(modeA.tangentialAccel);

    CC_SAFE_FREE(modeB.angle);
    CC_SAFE_FREE(modeB.degreesPerSecond);
    CC_SAFE_FREE(modeB.deltaRadius);
    CC_SAFE_FREE(modeB.radius);
}

Vector<ParticleSystem*> ParticleSystem::__allInstances;
float ParticleSystem::__totalParticleCountFactor = 1.0f;

ParticleSystem::ParticleSystem()
    : _isBlendAdditive(false)
    , _isAutoRemoveOnFinish(false)
    , _plistFile("")
    , _elapsed(0)
    , _configName("")
    , _emitCounter(0)
    , _batchNode(nullptr)
    , _atlasIndex(0)
    , _transformSystemDirty(false)
    , _allocatedParticles(0)
    , _isActive(true)
    , _particleCount(0)
    , _duration(0)
    , _life(0)
    , _lifeVar(0)
    , _angle(0)
    , _angleVar(0)
    , _emitterMode(Mode::GRAVITY)
    , _startSize(0)
    , _startSizeVar(0)
    , _endSize(0)
    , _endSizeVar(0)
    , _startSpin(0)
    , _startSpinVar(0)
    , _endSpin(0)
    , _endSpinVar(0)
    , _emissionRate(0)
    , _totalParticles(0)
    , _texture(nullptr)
    , _blendFunc(BlendFunc::ALPHA_PREMULTIPLIED)
    , _opacityModifyRGB(false)
    , _isLifeAnimated(false)
    , _isEmitterAnimated(false)
    , _isLoopAnimated(false)
    , _isAnimationAtlas(false)
    , _animDir(TexAnimDir::VERTICAL)
    , _animUnifiedSize(1)
    , _animIndexCount(0)
    , _isLifeAnimationReversed(false)
    , _isAnimationMulti(false)
    , _yCoordFlipped(1)
    , _positionType(PositionType::FREE)
    , _paused(false)
    , _sourcePositionCompatible(true)  // In the furture this member's default value maybe false or be removed.
{
    modeA.gravity.setZero();
    modeA.speed              = 0;
    modeA.speedVar           = 0;
    modeA.tangentialAccel    = 0;
    modeA.tangentialAccelVar = 0;
    modeA.radialAccel        = 0;
    modeA.radialAccelVar     = 0;
    modeA.rotationIsDir      = false;
    modeB.startRadius        = 0;
    modeB.startRadiusVar     = 0;
    modeB.endRadius          = 0;
    modeB.endRadiusVar       = 0;
    modeB.rotatePerSecond    = 0;
    modeB.rotatePerSecondVar = 0;
}
// implementation ParticleSystem

ParticleSystem* ParticleSystem::create(std::string_view plistFile)
{
    ParticleSystem* ret = new ParticleSystem();
    if (ret->initWithFile(plistFile))
    {
        ret->autorelease();
        return ret;
    }
    CC_SAFE_DELETE(ret);
    return ret;
}

ParticleSystem* ParticleSystem::createWithTotalParticles(int numberOfParticles)
{
    ParticleSystem* ret = new ParticleSystem();
    if (ret->initWithTotalParticles(numberOfParticles))
    {
        ret->autorelease();
        return ret;
    }
    CC_SAFE_DELETE(ret);
    return ret;
}

// static
Vector<ParticleSystem*>& ParticleSystem::getAllParticleSystems()
{
    return __allInstances;
}

void ParticleSystem::setTotalParticleCountFactor(float factor)
{
    __totalParticleCountFactor = factor;
}

bool ParticleSystem::init()
{
    return initWithTotalParticles(150);
}

bool ParticleSystem::initWithFile(std::string_view plistFile)
{
    bool ret      = false;
    _plistFile    = FileUtils::getInstance()->fullPathForFilename(plistFile);
    ValueMap dict = FileUtils::getInstance()->getValueMapFromFile(_plistFile);

    CCASSERT(!dict.empty(), "Particles: file not found");

    // FIXME: compute path from a path, should define a function somewhere to do it
    auto listFilePath = plistFile;
    if (listFilePath.find('/') != string::npos)
    {
        listFilePath = listFilePath.substr(0, listFilePath.rfind('/') + 1);
        ret          = this->initWithDictionary(dict, listFilePath);
    }
    else
    {
        ret = this->initWithDictionary(dict, "");
    }

    return ret;
}

bool ParticleSystem::initWithDictionary(const ValueMap& dictionary)
{
    return initWithDictionary(dictionary, "");
}

bool ParticleSystem::initWithDictionary(const ValueMap& dictionary, std::string_view dirname)
{
    bool ret              = false;
    unsigned char* buffer = nullptr;
    Image* image          = nullptr;
    do
    {
        int maxParticles = optValue(dictionary, "maxParticles").asInt();
        // self, not super
        if (this->initWithTotalParticles(maxParticles))
        {
            // Emitter name in particle designer 2.0
            _configName = optValue(dictionary, "configName").asString();

            // angle
            _angle    = optValue(dictionary, "angle").asFloat();
            _angleVar = optValue(dictionary, "angleVariance").asFloat();

            // duration
            _duration = optValue(dictionary, "duration").asFloat();

            // blend function
            if (!_configName.empty())
            {
                _blendFunc.src = utils::toBackendBlendFactor((int)optValue(dictionary, "blendFuncSource").asFloat());
            }
            else
            {
                _blendFunc.src = utils::toBackendBlendFactor(optValue(dictionary, "blendFuncSource").asInt());
            }
            _blendFunc.dst = utils::toBackendBlendFactor(optValue(dictionary, "blendFuncDestination").asInt());

            // color
            _startColor.r = optValue(dictionary, "startColorRed").asFloat();
            _startColor.g = optValue(dictionary, "startColorGreen").asFloat();
            _startColor.b = optValue(dictionary, "startColorBlue").asFloat();
            _startColor.a = optValue(dictionary, "startColorAlpha").asFloat();

            _startColorVar.r = optValue(dictionary, "startColorVarianceRed").asFloat();
            _startColorVar.g = optValue(dictionary, "startColorVarianceGreen").asFloat();
            _startColorVar.b = optValue(dictionary, "startColorVarianceBlue").asFloat();
            _startColorVar.a = optValue(dictionary, "startColorVarianceAlpha").asFloat();

            _endColor.r = optValue(dictionary, "finishColorRed").asFloat();
            _endColor.g = optValue(dictionary, "finishColorGreen").asFloat();
            _endColor.b = optValue(dictionary, "finishColorBlue").asFloat();
            _endColor.a = optValue(dictionary, "finishColorAlpha").asFloat();

            _endColorVar.r = optValue(dictionary, "finishColorVarianceRed").asFloat();
            _endColorVar.g = optValue(dictionary, "finishColorVarianceGreen").asFloat();
            _endColorVar.b = optValue(dictionary, "finishColorVarianceBlue").asFloat();
            _endColorVar.a = optValue(dictionary, "finishColorVarianceAlpha").asFloat();

            // particle size
            _startSize    = optValue(dictionary, "startParticleSize").asFloat();
            _startSizeVar = optValue(dictionary, "startParticleSizeVariance").asFloat();
            _endSize      = optValue(dictionary, "finishParticleSize").asFloat();
            _endSizeVar   = optValue(dictionary, "finishParticleSizeVariance").asFloat();

            // position
            float x = optValue(dictionary, "sourcePositionx").asFloat();
            float y = optValue(dictionary, "sourcePositiony").asFloat();
            if (!_sourcePositionCompatible)
            {
                this->setSourcePosition(Vec2(x, y));
            }
            else
            {
                this->setPosition(Vec2(x, y));
            }
            _posVar.x = optValue(dictionary, "sourcePositionVariancex").asFloat();
            _posVar.y = optValue(dictionary, "sourcePositionVariancey").asFloat();

            // Spinning
            _startSpin    = optValue(dictionary, "rotationStart").asFloat();
            _startSpinVar = optValue(dictionary, "rotationStartVariance").asFloat();
            _endSpin      = optValue(dictionary, "rotationEnd").asFloat();
            _endSpinVar   = optValue(dictionary, "rotationEndVariance").asFloat();

            _emitterMode = (Mode)optValue(dictionary, "emitterType").asInt();

            // Mode A: Gravity + tangential accel + radial accel
            if (_emitterMode == Mode::GRAVITY)
            {
                // gravity
                modeA.gravity.x = optValue(dictionary, "gravityx").asFloat();
                modeA.gravity.y = optValue(dictionary, "gravityy").asFloat();

                // speed
                modeA.speed    = optValue(dictionary, "speed").asFloat();
                modeA.speedVar = optValue(dictionary, "speedVariance").asFloat();

                // radial acceleration
                modeA.radialAccel    = optValue(dictionary, "radialAcceleration").asFloat();
                modeA.radialAccelVar = optValue(dictionary, "radialAccelVariance").asFloat();

                // tangential acceleration
                modeA.tangentialAccel    = optValue(dictionary, "tangentialAcceleration").asFloat();
                modeA.tangentialAccelVar = optValue(dictionary, "tangentialAccelVariance").asFloat();

                // rotation is dir
                modeA.rotationIsDir = optValue(dictionary, "rotationIsDir").asBool();
            }

            // or Mode B: radius movement
            else if (_emitterMode == Mode::RADIUS)
            {
                if (!_configName.empty())
                {
                    modeB.startRadius = optValue(dictionary, "maxRadius").asInt();
                }
                else
                {
                    modeB.startRadius = optValue(dictionary, "maxRadius").asFloat();
                }
                modeB.startRadiusVar = optValue(dictionary, "maxRadiusVariance").asFloat();
                if (!_configName.empty())
                {
                    modeB.endRadius = optValue(dictionary, "minRadius").asInt();
                }
                else
                {
                    modeB.endRadius = optValue(dictionary, "minRadius").asFloat();
                }

                modeB.endRadiusVar = optValue(dictionary, "minRadiusVariance").asFloat();

                if (!_configName.empty())
                {
                    modeB.rotatePerSecond = optValue(dictionary, "rotatePerSecond").asInt();
                }
                else
                {
                    modeB.rotatePerSecond = optValue(dictionary, "rotatePerSecond").asFloat();
                }
                modeB.rotatePerSecondVar = optValue(dictionary, "rotatePerSecondVariance").asFloat();
            }
            else
            {
                CCASSERT(false, "Invalid emitterType in config file");
                CC_BREAK_IF(true);
            }

            // life span
            _life    = optValue(dictionary, "particleLifespan").asFloat();
            _lifeVar = optValue(dictionary, "particleLifespanVariance").asFloat();

            // emission Rate
            _emissionRate = _totalParticles / _life;

            // don't get the internal texture if a batchNode is used
            if (!_batchNode)
            {
                // Set a compatible default for the alpha transfer
                _opacityModifyRGB = false;

                // texture
                // Try to get the texture from the cache
                std::string textureName = optValue(dictionary, "textureFileName").asString();

                size_t rPos = textureName.rfind('/');

                if (rPos != string::npos)
                {
                    string textureDir = textureName.substr(0, rPos + 1);

                    if (!dirname.empty() && textureDir != dirname)
                    {
                        textureName = textureName.substr(rPos + 1);
                        textureName.insert(0, dirname);  // textureName = dirname + textureName;
                    }
                }
                else if (!dirname.empty() && !textureName.empty())
                {
                    textureName.insert(0, dirname);  // textureName = dirname + textureName;
                }

                Texture2D* tex = nullptr;

                if (!textureName.empty())
                {
                    // set not pop-up message box when load image failed
                    bool notify = FileUtils::getInstance()->isPopupNotify();
                    FileUtils::getInstance()->setPopupNotify(false);
                    tex = _director->getTextureCache()->addImage(textureName);
                    // reset the value of UIImage notify
                    FileUtils::getInstance()->setPopupNotify(notify);
                }

                if (tex)
                {
                    setTexture(tex);
                }
                else if (dictionary.find("textureImageData") != dictionary.end())
                {
                    std::string textureData = dictionary.at("textureImageData").asString();
                    CCASSERT(!textureData.empty(), "textureData can't be empty!");

                    auto dataLen = textureData.size();
                    if (dataLen != 0)
                    {
                        // if it fails, try to get it from the base64-gzipped data
                        int decodeLen =
                            base64Decode((unsigned char*)textureData.c_str(), (unsigned int)dataLen, &buffer);
                        CCASSERT(buffer != nullptr, "CCParticleSystem: error decoding textureImageData");
                        CC_BREAK_IF(!buffer);

                        unsigned char* deflated = nullptr;
                        ssize_t deflatedLen     = ZipUtils::inflateMemory(buffer, decodeLen, &deflated);
                        CCASSERT(deflated != nullptr, "CCParticleSystem: error ungzipping textureImageData");
                        CC_BREAK_IF(!deflated);

                        // For android, we should retain it in VolatileTexture::addImage which invoked in
                        // Director::getInstance()->getTextureCache()->addUIImage()
                        image     = new Image();
                        bool isOK = image->initWithImageData(deflated, deflatedLen, true);
                        CCASSERT(isOK, "CCParticleSystem: error init image with Data");
                        CC_BREAK_IF(!isOK);

                        setTexture(_director->getTextureCache()->addImage(image, _plistFile + textureName));

                        image->release();
                    }
                }

                _yCoordFlipped = optValue(dictionary, "yCoordFlipped").asInt(1);

                if (!this->_texture)
                    CCLOGWARN("cocos2d: Warning: ParticleSystemQuad system without a texture");
            }
            ret = true;
        }
    } while (0);
    free(buffer);
    return ret;
}

bool ParticleSystem::initWithTotalParticles(int numberOfParticles)
{
    _totalParticles = numberOfParticles;

    _particleData.release();

    if (!_particleData.init(_totalParticles))
    {
        CCLOG("Particle system: not enough memory");
        this->release();
        return false;
    }
    _allocatedParticles = numberOfParticles;

    if (_batchNode)
    {
        for (int i = 0; i < _totalParticles; i++)
        {
            _particleData.atlasIndex[i] = i;
        }
    }
    // default, active
    _isActive = true;

    // default blend function
    _blendFunc = BlendFunc::ALPHA_PREMULTIPLIED;

    // default movement type;
    _positionType = PositionType::FREE;

    // by default be in mode A:
    _emitterMode = Mode::GRAVITY;

    // default: modulate
    // FIXME:: not used
    //    colorModulate = YES;

    _isAutoRemoveOnFinish = false;

    // Optimization: compile updateParticle method
    // updateParticleSel = @selector(updateQuadWithParticle:newPosition:);
    // updateParticleImp = (CC_UPDATE_PARTICLE_IMP) [self methodForSelector:updateParticleSel];
    // for batchNode
    _transformSystemDirty = false;

    return true;
}

ParticleSystem::~ParticleSystem()
{
    // Since the scheduler retains the "target (in this case the ParticleSystem)
    // it is not needed to call "unscheduleUpdate" here. In fact, it will be called in "cleanup"
    // unscheduleUpdate();
    _particleData.release();
    _animations.clear();
    CC_SAFE_RELEASE(_texture);
}

void ParticleSystem::addParticles(int count, int animationCellIndex, int animationIndex)
{
    if (_paused)
        return;
    uint32_t RANDSEED = rand();

    if (_isAnimationAtlas)
    {
        animationCellIndex = MIN(animationCellIndex, getTotalAnimationCells() - 1);
        animationIndex     = MIN(animationIndex, _animIndexCount - 1);
    }

    int start = _particleCount;
    _particleCount += count;

    // life
    for (int i = start; i < _particleCount; ++i)
    {
        float particleLife               = _life + _lifeVar * RANDOM_M11(&RANDSEED);
        _particleData.totalTimeToLive[i] = MAX(0, particleLife);
        _particleData.timeToLive[i]      = MAX(0, particleLife);
    }

    // position
    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.posx[i] = _sourcePosition.x + _posVar.x * RANDOM_M11(&RANDSEED);
    }

    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.posy[i] = _sourcePosition.y + _posVar.y * RANDOM_M11(&RANDSEED);
    }

    if (animationCellIndex == -1 && _isEmitterAnimated)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.animCellIndex[i] = (int)abs(RANDOM_M11(&RANDSEED) * getTotalAnimationCells());
        }
    }

    if (animationCellIndex != -1)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.animCellIndex[i] = animationCellIndex;
        }
    }

    if (animationIndex == -1 && !_isAnimationMulti && _isLoopAnimated)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.animIndex[i] = 0;
            auto descriptor            = _animations.at(_particleData.animIndex[i]);
            _particleData.animTimeLength[i] =
                descriptor.animationSpeed + descriptor.animationSpeedVariance * RANDOM_M11(&RANDSEED);
        }
    }

    if (animationIndex == -1 && _isAnimationMulti && _isLoopAnimated)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.animIndex[i] = _randomAnimations[abs(RANDOM_M11(&RANDSEED) * _randomAnimations.size())];
            auto descriptor = _animations.at(_particleData.animIndex[i]);
            _particleData.animTimeLength[i] =
                descriptor.animationSpeed + descriptor.animationSpeedVariance * RANDOM_M11(&RANDSEED);
        }
    }

    if (_isLoopAnimated)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.animTimeDelta[i] = 0;
        }
    }

    if (animationIndex != -1)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.animIndex[i] = animationIndex;
            auto descriptor            = _animations.at(_particleData.animIndex[i]);
            _particleData.animTimeLength[i] =
                descriptor.animationSpeed + descriptor.animationSpeedVariance * RANDOM_M11(&RANDSEED);
        }
    }

    // color
#define SET_COLOR(c, b, v)                                  \
    for (int i = start; i < _particleCount; ++i)            \
    {                                                       \
        c[i] = clampf(b + v * RANDOM_M11(&RANDSEED), 0, 1); \
    }

    SET_COLOR(_particleData.colorR, _startColor.r, _startColorVar.r);
    SET_COLOR(_particleData.colorG, _startColor.g, _startColorVar.g);
    SET_COLOR(_particleData.colorB, _startColor.b, _startColorVar.b);
    SET_COLOR(_particleData.colorA, _startColor.a, _startColorVar.a);

    SET_COLOR(_particleData.deltaColorR, _endColor.r, _endColorVar.r);
    SET_COLOR(_particleData.deltaColorG, _endColor.g, _endColorVar.g);
    SET_COLOR(_particleData.deltaColorB, _endColor.b, _endColorVar.b);
    SET_COLOR(_particleData.deltaColorA, _endColor.a, _endColorVar.a);

#define SET_DELTA_COLOR(c, dc)                                \
    for (int i = start; i < _particleCount; ++i)              \
    {                                                         \
        dc[i] = (dc[i] - c[i]) / _particleData.timeToLive[i]; \
    }

    SET_DELTA_COLOR(_particleData.colorR, _particleData.deltaColorR);
    SET_DELTA_COLOR(_particleData.colorG, _particleData.deltaColorG);
    SET_DELTA_COLOR(_particleData.colorB, _particleData.deltaColorB);
    SET_DELTA_COLOR(_particleData.colorA, _particleData.deltaColorA);

    // size
    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.size[i] = _startSize + _startSizeVar * RANDOM_M11(&RANDSEED);
        _particleData.size[i] = MAX(0, _particleData.size[i]);
    }

    if (_endSize != START_SIZE_EQUAL_TO_END_SIZE)
    {
        for (int i = start; i < _particleCount; ++i)
        {
            float endSize              = _endSize + _endSizeVar * RANDOM_M11(&RANDSEED);
            endSize                    = MAX(0, endSize);
            _particleData.deltaSize[i] = (endSize - _particleData.size[i]) / _particleData.timeToLive[i];
        }
    }
    else
    {
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.deltaSize[i] = 0.0f;
        }
    }

    // rotation
    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.rotation[i] = _startSpin + _startSpinVar * RANDOM_M11(&RANDSEED);
    }
    for (int i = start; i < _particleCount; ++i)
    {
        float endA                     = _endSpin + _endSpinVar * RANDOM_M11(&RANDSEED);
        _particleData.deltaRotation[i] = (endA - _particleData.rotation[i]) / _particleData.timeToLive[i];
    }

    // static rotation
    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.staticRotation[i] = _staticRotation + _staticRotationVar * RANDOM_M11(&RANDSEED);
    }

    // position
    Vec2 pos;
    if (_positionType == PositionType::FREE)
    {
        pos = this->convertToWorldSpace(Vec2::ZERO);
    }
    else if (_positionType == PositionType::RELATIVE)
    {
        pos = _position;
    }
    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.startPosX[i] = pos.x;
    }
    for (int i = start; i < _particleCount; ++i)
    {
        _particleData.startPosY[i] = pos.y;
    }

    // Mode Gravity: A
    if (_emitterMode == Mode::GRAVITY)
    {

        // radial accel
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.modeA.radialAccel[i] = modeA.radialAccel + modeA.radialAccelVar * RANDOM_M11(&RANDSEED);
        }

        // tangential accel
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.modeA.tangentialAccel[i] =
                modeA.tangentialAccel + modeA.tangentialAccelVar * RANDOM_M11(&RANDSEED);
        }

        // rotation is dir
        if (modeA.rotationIsDir)
        {
            for (int i = start; i < _particleCount; ++i)
            {
                float a = CC_DEGREES_TO_RADIANS(_angle + _angleVar * RANDOM_M11(&RANDSEED));
                Vec2 v(cosf(a), sinf(a));
                float s                     = modeA.speed + modeA.speedVar * RANDOM_M11(&RANDSEED);
                Vec2 dir                    = v * s;
                _particleData.modeA.dirX[i] = dir.x;  // v * s ;
                _particleData.modeA.dirY[i] = dir.y;
                _particleData.rotation[i]   = -CC_RADIANS_TO_DEGREES(dir.getAngle());
            }
        }
        else
        {
            for (int i = start; i < _particleCount; ++i)
            {
                float a = CC_DEGREES_TO_RADIANS(_angle + _angleVar * RANDOM_M11(&RANDSEED));
                Vec2 v(cosf(a), sinf(a));
                float s                     = modeA.speed + modeA.speedVar * RANDOM_M11(&RANDSEED);
                Vec2 dir                    = v * s;
                _particleData.modeA.dirX[i] = dir.x;  // v * s ;
                _particleData.modeA.dirY[i] = dir.y;
            }
        }
    }

    // Mode Radius: B
    else
    {
        // Need to check by Jacky
        //  Set the default diameter of the particle from the source position
        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.modeB.radius[i] = modeB.startRadius + modeB.startRadiusVar * RANDOM_M11(&RANDSEED);
        }

        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.modeB.angle[i] = CC_DEGREES_TO_RADIANS(_angle + _angleVar * RANDOM_M11(&RANDSEED));
        }

        for (int i = start; i < _particleCount; ++i)
        {
            _particleData.modeB.degreesPerSecond[i] =
                CC_DEGREES_TO_RADIANS(modeB.rotatePerSecond + modeB.rotatePerSecondVar * RANDOM_M11(&RANDSEED));
        }

        if (modeB.endRadius == START_RADIUS_EQUAL_TO_END_RADIUS)
        {
            for (int i = start; i < _particleCount; ++i)
            {
                _particleData.modeB.deltaRadius[i] = 0.0f;
            }
        }
        else
        {
            for (int i = start; i < _particleCount; ++i)
            {
                float endRadius = modeB.endRadius + modeB.endRadiusVar * RANDOM_M11(&RANDSEED);
                _particleData.modeB.deltaRadius[i] =
                    (endRadius - _particleData.modeB.radius[i]) / _particleData.timeToLive[i];
            }
        }
    }
}

void ParticleSystem::setAnimationDescriptor(unsigned short indexOfDescriptor,
                                            float time,
                                            float timeVariance,
                                            std::vector<unsigned short> indices,
                                            bool reverse)
{
    ParticleAnimationDescriptor desc{};

    desc.animationSpeed         = time;
    desc.animationSpeedVariance = timeVariance;
    desc.animationIndices       = indices;
    desc.reverseIndices         = reverse;

    if (_animations.find(indexOfDescriptor) == _animations.end())
        _animations.insert({indexOfDescriptor, desc});
    else
    {
        _animations.erase(indexOfDescriptor);
        _animations.insert({indexOfDescriptor, desc});
    }
}

void ParticleSystem::resetAnimationIndices()
{
    _animIndexCount = 0;
    _animationIndices.clear();
}

void ParticleSystem::resetAnimationDescriptors()
{
    _animations.clear();
    _randomAnimations.clear();
}

void ParticleSystem::setMultiAnimationRandom()
{
    _randomAnimations.clear();
    for (auto& a : _animations)
        _randomAnimations.push_back(a.first);
}

void ParticleSystem::addAnimationIndex(std::string_view frameName)
{
    addAnimationIndex(_animIndexCount++, frameName);
}

void ParticleSystem::addAnimationIndex(unsigned short index, std::string_view frameName)
{
    auto frame = SpriteFrameCache::getInstance()->getSpriteFrameByName(frameName);

    if (frame)
        addAnimationIndex(index, frame);
 }

void ParticleSystem::addAnimationIndex(cocos2d::SpriteFrame* frame)
{
    addAnimationIndex(_animIndexCount++, frame);
}

void ParticleSystem::addAnimationIndex(unsigned short index, cocos2d::SpriteFrame* frame)
{
    //Not sure how to check texture equality truly but it won't hurt to skip it
    //CCASSERT(frame->getTexture() == _texture, "Sprite frame texture and particle system texture should match!");

    ParticleFrameDescriptor desc{};

    desc.rect      = frame->getRect();
    desc.isRotated = frame->isRotated();

    if (_animationIndices.find(index) == _animationIndices.end())
        _animationIndices.insert({index, desc});
    else
    {
        _animationIndices.erase(index);
        _animationIndices.insert({index, desc});
    }
}

void ParticleSystem::onEnter()
{
    Node::onEnter();

    // update after action in run!
    this->scheduleUpdateWithPriority(1);

    __allInstances.pushBack(this);
}

void ParticleSystem::onExit()
{
    this->unscheduleUpdate();
    Node::onExit();

    auto iter = std::find(std::begin(__allInstances), std::end(__allInstances), this);
    if (iter != std::end(__allInstances))
    {
        __allInstances.erase(iter);
    }
}

void ParticleSystem::stopSystem()
{
    _isActive    = false;
    _elapsed     = _duration;
    _emitCounter = 0;
}

void ParticleSystem::resetSystem()
{
    _isActive = true;
    _elapsed  = 0;
    for (int i = 0; i < _particleCount; ++i)
    {
        _particleData.timeToLive[i] = 0.0f;
    }
}

bool ParticleSystem::isFull()
{
    return (_particleCount == _totalParticles);
}

// ParticleSystem - MainLoop
void ParticleSystem::update(float dt)
{
    CC_PROFILER_START_CATEGORY(kProfilerCategoryParticles, "CCParticleSystem - update");

    if (_isActive && _emissionRate)
    {
        float rate         = 1.0f / _emissionRate;
        int totalParticles = static_cast<int>(_totalParticles * __totalParticleCountFactor);

        // issue #1201, prevent bursts of particles, due to too high emitCounter
        if (_particleCount < totalParticles)
        {
            _emitCounter += dt;
            if (_emitCounter < 0.f)
                _emitCounter = 0.f;
        }

        int emitCount = MIN(totalParticles - _particleCount, _emitCounter / rate);
        addParticles(emitCount);
        _emitCounter -= rate * emitCount;

        _elapsed += dt;
        if (_elapsed < 0.f)
            _elapsed = 0.f;
        if (_duration != DURATION_INFINITY && _duration < _elapsed)
        {
            this->stopSystem();
        }
    }

    {
        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.timeToLive[i] -= dt;
            if (_isLifeAnimated && _animations.empty())
            {
                float percent = (_particleData.totalTimeToLive[i] - _particleData.timeToLive[i]) / _particleData.totalTimeToLive[i];
                percent = _isLifeAnimationReversed ? 1.0F - percent : percent;
                _particleData.animCellIndex[i] = (unsigned int)MIN((percent * getTotalAnimationCells()), getTotalAnimationCells() - 1);
            }
            if (_isLifeAnimated && !_animations.empty())
            {
                auto& anim = _animations.begin()->second;

                float percent =
                    (_particleData.totalTimeToLive[i] - _particleData.timeToLive[i]) / _particleData.totalTimeToLive[i];

                percent                        = (!!_isLifeAnimationReversed != !!anim.reverseIndices) ? 1.0F - percent : percent;
                _particleData.animCellIndex[i] = anim.animationIndices[MIN(abs(percent * anim.animationIndices.size()),
                                                                           anim.animationIndices.size() - 1)];
            }
            if (_isLoopAnimated)
            {
                auto& anim = _animations.at(_particleData.animIndex[i]);

                _particleData.animTimeDelta[i] += dt;
                if (_particleData.animTimeDelta[i] >= _particleData.animTimeLength[i])
                    _particleData.animTimeDelta[i] = 0;

                float percent = _particleData.animTimeDelta[i] / _particleData.animTimeLength[i];

                percent = anim.reverseIndices ? 1.0F - percent : percent;
                _particleData.animCellIndex[i] = anim.animationIndices[MIN(abs(percent * anim.animationIndices.size()),
                                                                           anim.animationIndices.size() - 1)];
            }
        }

        for (int i = 0; i < _particleCount; ++i)
        {
            if (_particleData.timeToLive[i] <= 0.0f)
            {
                int j = _particleCount - 1;
                while (j > 0 && _particleData.timeToLive[j] <= 0)
                {
                    _particleCount--;
                    j--;
                }
                _particleData.copyParticle(i, _particleCount - 1);
                if (_batchNode)
                {
                    // disable the switched particle
                    int currentIndex = _particleData.atlasIndex[i];
                    _batchNode->disableParticle(_atlasIndex + currentIndex);
                    // switch indexes
                    _particleData.atlasIndex[_particleCount - 1] = currentIndex;
                }
                --_particleCount;
                if (_particleCount == 0 && _isAutoRemoveOnFinish)
                {
                    this->unscheduleUpdate();
                    _parent->removeChild(this, true);
                    return;
                }
            }
        }

        if (_emitterMode == Mode::GRAVITY)
        {
            for (int i = 0; i < _particleCount; ++i)
            {
                particle_point tmp, radial = {0.0f, 0.0f}, tangential;

                // radial acceleration
                if (_particleData.posx[i] || _particleData.posy[i])
                {
                    normalize_point(_particleData.posx[i], _particleData.posy[i], &radial);
                }
                tangential = radial;
                radial.x *= _particleData.modeA.radialAccel[i];
                radial.y *= _particleData.modeA.radialAccel[i];

                // tangential acceleration
                std::swap(tangential.x, tangential.y);
                tangential.x *= -_particleData.modeA.tangentialAccel[i];
                tangential.y *= _particleData.modeA.tangentialAccel[i];

                // (gravity + radial + tangential) * dt
                tmp.x = radial.x + tangential.x + modeA.gravity.x;
                tmp.y = radial.y + tangential.y + modeA.gravity.y;
                tmp.x *= dt;
                tmp.y *= dt;

                _particleData.modeA.dirX[i] += tmp.x;
                _particleData.modeA.dirY[i] += tmp.y;

                // this is cocos2d-x v3.0
                // if (_configName.length()>0 && _yCoordFlipped != -1)

                // this is cocos2d-x v3.0
                tmp.x = _particleData.modeA.dirX[i] * dt * _yCoordFlipped;
                tmp.y = _particleData.modeA.dirY[i] * dt * _yCoordFlipped;
                _particleData.posx[i] += tmp.x;
                _particleData.posy[i] += tmp.y;
            }
        }
        else
        {
            // Why use so many for-loop separately instead of putting them together?
            // When the processor needs to read from or write to a location in memory,
            // it first checks whether a copy of that data is in the cache.
            // And every property's memory of the particle system is continuous,
            // for the purpose of improving cache hit rate, we should process only one property in one for-loop AFAP.
            // It was proved to be effective especially for low-end machine.
            for (int i = 0; i < _particleCount; ++i)
            {
                _particleData.modeB.angle[i] += _particleData.modeB.degreesPerSecond[i] * dt;
            }

            for (int i = 0; i < _particleCount; ++i)
            {
                _particleData.modeB.radius[i] += _particleData.modeB.deltaRadius[i] * dt;
            }

            for (int i = 0; i < _particleCount; ++i)
            {
                _particleData.posx[i] = -cosf(_particleData.modeB.angle[i]) * _particleData.modeB.radius[i];
            }
            for (int i = 0; i < _particleCount; ++i)
            {
                _particleData.posy[i] =
                    -sinf(_particleData.modeB.angle[i]) * _particleData.modeB.radius[i] * _yCoordFlipped;
            }
        }

        // color r,g,b,a
        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.colorR[i] += _particleData.deltaColorR[i] * dt;
        }

        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.colorG[i] += _particleData.deltaColorG[i] * dt;
        }

        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.colorB[i] += _particleData.deltaColorB[i] * dt;
        }

        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.colorA[i] += _particleData.deltaColorA[i] * dt;
        }
        // size
        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.size[i] += (_particleData.deltaSize[i] * dt);
            _particleData.size[i] = MAX(0, _particleData.size[i]);
        }
        // angle
        for (int i = 0; i < _particleCount; ++i)
        {
            _particleData.rotation[i] += _particleData.deltaRotation[i] * dt;
        }

        updateParticleQuads();
        _transformSystemDirty = false;
    }

    // only update gl buffer when visible
    if (_visible && !_batchNode)
    {
        postStep();
    }

    CC_PROFILER_STOP_CATEGORY(kProfilerCategoryParticles, "CCParticleSystem - update");
}

void ParticleSystem::updateWithNoTime()
{
    this->update(0.0f);
}

void ParticleSystem::updateParticleQuads()
{
    // should be overridden
}

void ParticleSystem::postStep()
{
    // should be overridden
}

// ParticleSystem - Texture protocol
void ParticleSystem::setTexture(Texture2D* var)
{
    if (_texture != var)
    {
        CC_SAFE_RETAIN(var);
        CC_SAFE_RELEASE(_texture);
        _texture = var;
        updateBlendFunc();
    }
}

void ParticleSystem::updateBlendFunc()
{
    CCASSERT(!_batchNode, "Can't change blending functions when the particle is being batched");

    if (_texture)
    {
        bool premultiplied = _texture->hasPremultipliedAlpha();

        _opacityModifyRGB = false;

        if (_texture && (_blendFunc.src == CC_BLEND_SRC && _blendFunc.dst == CC_BLEND_DST))
        {
            if (premultiplied)
            {
                _opacityModifyRGB = true;
            }
            else
            {
                _blendFunc = BlendFunc::ALPHA_NON_PREMULTIPLIED;
            }
        }
    }
}

Texture2D* ParticleSystem::getTexture() const
{
    return _texture;
}

// ParticleSystem - Additive Blending
void ParticleSystem::setBlendAdditive(bool additive)
{
    if (additive)
    {
        _blendFunc = BlendFunc::ADDITIVE;
    }
    else
    {
        if (_texture && !_texture->hasPremultipliedAlpha())
            _blendFunc = BlendFunc::ALPHA_NON_PREMULTIPLIED;
        else
            _blendFunc = BlendFunc::ALPHA_PREMULTIPLIED;
    }
}

bool ParticleSystem::isBlendAdditive() const
{
    return (_blendFunc.src == backend::BlendFactor::SRC_ALPHA && _blendFunc.dst == backend::BlendFactor::ONE);
}

// ParticleSystem - Properties of Gravity Mode
void ParticleSystem::setTangentialAccel(float t)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.tangentialAccel = t;
}

float ParticleSystem::getTangentialAccel() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.tangentialAccel;
}

void ParticleSystem::setTangentialAccelVar(float t)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.tangentialAccelVar = t;
}

float ParticleSystem::getTangentialAccelVar() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.tangentialAccelVar;
}

void ParticleSystem::setRadialAccel(float t)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.radialAccel = t;
}

float ParticleSystem::getRadialAccel() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.radialAccel;
}

void ParticleSystem::setRadialAccelVar(float t)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.radialAccelVar = t;
}

float ParticleSystem::getRadialAccelVar() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.radialAccelVar;
}

void ParticleSystem::setRotationIsDir(bool t)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.rotationIsDir = t;
}

bool ParticleSystem::getRotationIsDir() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.rotationIsDir;
}

void ParticleSystem::setGravity(const Vec2& g)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.gravity = g;
}

const Vec2& ParticleSystem::getGravity()
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.gravity;
}

void ParticleSystem::setSpeed(float speed)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.speed = speed;
}

float ParticleSystem::getSpeed() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.speed;
}

void ParticleSystem::setSpeedVar(float speedVar)
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    modeA.speedVar = speedVar;
}

float ParticleSystem::getSpeedVar() const
{
    CCASSERT(_emitterMode == Mode::GRAVITY, "Particle Mode should be Gravity");
    return modeA.speedVar;
}

// ParticleSystem - Properties of Radius Mode
void ParticleSystem::setStartRadius(float startRadius)
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    modeB.startRadius = startRadius;
}

float ParticleSystem::getStartRadius() const
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    return modeB.startRadius;
}

void ParticleSystem::setStartRadiusVar(float startRadiusVar)
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    modeB.startRadiusVar = startRadiusVar;
}

float ParticleSystem::getStartRadiusVar() const
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    return modeB.startRadiusVar;
}

void ParticleSystem::setEndRadius(float endRadius)
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    modeB.endRadius = endRadius;
}

float ParticleSystem::getEndRadius() const
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    return modeB.endRadius;
}

void ParticleSystem::setEndRadiusVar(float endRadiusVar)
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    modeB.endRadiusVar = endRadiusVar;
}

float ParticleSystem::getEndRadiusVar() const
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    return modeB.endRadiusVar;
}

void ParticleSystem::setRotatePerSecond(float degrees)
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    modeB.rotatePerSecond = degrees;
}

float ParticleSystem::getRotatePerSecond() const
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    return modeB.rotatePerSecond;
}

void ParticleSystem::setRotatePerSecondVar(float degrees)
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    modeB.rotatePerSecondVar = degrees;
}

float ParticleSystem::getRotatePerSecondVar() const
{
    CCASSERT(_emitterMode == Mode::RADIUS, "Particle Mode should be Radius");
    return modeB.rotatePerSecondVar;
}

bool ParticleSystem::isActive() const
{
    return _isActive;
}

int ParticleSystem::getTotalParticles() const
{
    return _totalParticles;
}

void ParticleSystem::setTotalParticles(int var)
{
    CCASSERT(var <= _allocatedParticles, "Particle: resizing particle array only supported for quads");
    _totalParticles = var;
}

const BlendFunc& ParticleSystem::getBlendFunc() const
{
    return _blendFunc;
}

void ParticleSystem::setBlendFunc(const BlendFunc& blendFunc)
{
    if (_blendFunc.src != blendFunc.src || _blendFunc.dst != blendFunc.dst)
    {
        _blendFunc = blendFunc;
        this->updateBlendFunc();
    }
}

bool ParticleSystem::isAutoRemoveOnFinish() const
{
    return _isAutoRemoveOnFinish;
}

void ParticleSystem::setAutoRemoveOnFinish(bool var)
{
    _isAutoRemoveOnFinish = var;
}

// ParticleSystem - methods for batchNode rendering

ParticleBatchNode* ParticleSystem::getBatchNode() const
{
    return _batchNode;
}

void ParticleSystem::setBatchNode(ParticleBatchNode* batchNode)
{
    if (_batchNode != batchNode)
    {

        _batchNode = batchNode;  // weak reference

        if (batchNode)
        {
            // each particle needs a unique index
            for (int i = 0; i < _totalParticles; i++)
            {
                _particleData.atlasIndex[i] = i;
            }
        }
    }
}

// don't use a transform matrix, this is faster
void ParticleSystem::setScale(float s)
{
    _transformSystemDirty = true;
    Node::setScale(s);
}

void ParticleSystem::setRotation(float newRotation)
{
    _transformSystemDirty = true;
    Node::setRotation(newRotation);
}

void ParticleSystem::setScaleX(float newScaleX)
{
    _transformSystemDirty = true;
    Node::setScaleX(newScaleX);
}

void ParticleSystem::setScaleY(float newScaleY)
{
    _transformSystemDirty = true;
    Node::setScaleY(newScaleY);
}

void ParticleSystem::start()
{
    resetSystem();
}

void ParticleSystem::stop()
{
    stopSystem();
}

bool ParticleSystem::isPaused() const
{
    return _paused;
}

void ParticleSystem::pauseEmissions()
{
    _paused = true;
}

void ParticleSystem::resumeEmissions()
{
    _paused = false;
}

NS_CC_END
